"""
Secrets from a real Vault: the settings source and the one-time import. No mocks:
the policies, the AppRole sign-in and KV v2 are Vault's own behaviour.

Each test module starts a throwaway `vault server -dev` on a free port (the
Homebrew binary, installed by ./local/dev.sh install) and stops it afterwards;
the local Vault on :8200 is never touched. Skipped when vault is not installed.
"""

import json
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

from shared.settings import Settings
from shared.vault import VaultError, VaultSettingsSource

VAULT = shutil.which("vault")
IMPORT_SCRIPT = Path(__file__).resolve().parents[3] / "local" / "vault_import.py"
pytestmark = pytest.mark.skipif(VAULT is None, reason="vault is not installed (./local/dev.sh install)")


@dataclass(frozen=True)
class DevVault:
    address: str
    root_token: str

    def call(self, method: str, path: str, body: dict[str, object] | None = None) -> dict[str, object]:
        request = urllib.request.Request(
            f"{self.address}{path}",
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"X-Vault-Token": self.root_token},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = response.read()
        return json.loads(payload) if payload else {}

    def put(self, path: str, data: dict[str, str]) -> None:
        self.call("POST", f"/v1/secret/data/{path}", {"data": data})

    def get(self, path: str) -> dict[str, str]:
        return self.call("GET", f"/v1/secret/data/{path}")["data"]["data"]  # type: ignore[index]

    def role(self, name: str, readable: list[str], directory: Path) -> dict[str, str]:
        """An AppRole that may read only `readable`; the env vars a process would get."""
        policy = "\n".join(f'path "secret/data/{p}" {{ capabilities = ["read"] }}' for p in readable)
        self.call("PUT", f"/v1/sys/policies/acl/{name}", {"policy": policy})
        self.call("POST", f"/v1/auth/approle/role/{name}", {"token_policies": name})
        role_id = self.call("GET", f"/v1/auth/approle/role/{name}/role-id")["data"]["role_id"]  # type: ignore[index]
        secret_id = self.call("POST", f"/v1/auth/approle/role/{name}/secret-id")["data"]["secret_id"]  # type: ignore[index]
        (directory / f"{name}.role-id").write_text(str(role_id))
        (directory / f"{name}.secret-id").write_text(str(secret_id))
        return {
            "VAULT_ADDR": self.address,
            "VAULT_ROLE_ID_FILE": str(directory / f"{name}.role-id"),
            "VAULT_SECRET_ID_FILE": str(directory / f"{name}.secret-id"),
        }


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture(scope="module")
def vault() -> Iterator[DevVault]:
    port, token = _free_port(), uuid4().hex
    assert VAULT is not None
    server = subprocess.Popen(
        [VAULT, "server", "-dev", f"-dev-root-token-id={token}", f"-dev-listen-address=127.0.0.1:{port}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    dev = DevVault(f"http://127.0.0.1:{port}", token)
    try:
        for _ in range(100):
            try:
                dev.call("GET", "/v1/sys/health")
                break
            except OSError:
                time.sleep(0.1)
        dev.call("POST", "/v1/sys/auth/approle", {"type": "approle"})
        yield dev
    finally:
        server.terminate()
        server.wait(timeout=10)


class ServiceSettings(BaseSettings):
    """A service's settings in miniature: one shared and two per-service secrets."""

    POSTGRES_PASSWORD: str
    MAIL_PASSWORD: SecretStr | None = None
    STRIPE_SECRET_KEY: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("STRIPE_SECRET_KEY", "STRIPE_TEST_SECRET_KEY")
    )


def _settings(environ: dict[str, str]) -> ServiceSettings:
    class Configured(ServiceSettings):
        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            return (init_settings, VaultSettingsSource(settings_cls, environ=environ))

    return Configured()  # type: ignore[call-arg]


def _fake(label: str) -> str:
    """A throwaway test value, made at run time.

    Test values for password-named keys are never literals: secret scanners
    (GitGuardian's generic-password detector) report any literal assigned to
    such a key, fake or not.
    """
    return f"{label}-{uuid4().hex[:12]}"


# ------------------------------------------------------------- settings source


def test_a_service_reads_its_own_path_and_the_shared_infra(vault: DevVault, tmp_path: Path) -> None:
    database, infra_mail, own_mail = _fake("database"), _fake("infra-mail"), _fake("own-mail")
    vault.put("app/shared-infra", {"POSTGRES_PASSWORD": database, "MAIL_PASSWORD": infra_mail})
    # Built apart: a dict holding a password-named key carries no string literal.
    unrelated = {"UNRELATED": "dropped"}
    vault.put("app/notification-service", {"MAIL_PASSWORD": own_mail, **unrelated})
    environ = vault.role("notification", ["app/shared-infra", "app/notification-service"], tmp_path)
    environ["VAULT_SECRET_PATHS"] = "app/shared-infra,app/notification-service"

    settings = _settings(environ)

    assert settings.POSTGRES_PASSWORD == database
    assert settings.MAIL_PASSWORD is not None
    assert settings.MAIL_PASSWORD.get_secret_value() == own_mail  # the later path wins
    assert settings.STRIPE_SECRET_KEY is None  # another service's secret: never given


def test_an_old_alias_in_vault_is_accepted(vault: DevVault, tmp_path: Path) -> None:
    old_name_value = _fake("old-name")
    vault.put("app/payment-service", {"POSTGRES_PASSWORD": _fake("database"), "STRIPE_TEST_SECRET_KEY": old_name_value})
    environ = vault.role("payment", ["app/payment-service"], tmp_path)
    environ["VAULT_SECRET_PATHS"] = "app/payment-service"

    settings = _settings(environ)

    assert settings.STRIPE_SECRET_KEY is not None
    assert settings.STRIPE_SECRET_KEY.get_secret_value() == old_name_value


def test_another_services_path_is_refused_and_the_value_never_shown(vault: DevVault, tmp_path: Path) -> None:
    never_shown = _fake("never-shown")
    vault.put("app/payment-only", {"POSTGRES_PASSWORD": never_shown})
    environ = vault.role("cart", ["app/cart-service"], tmp_path)
    environ["VAULT_SECRET_PATHS"] = "app/payment-only"

    with pytest.raises(VaultError) as refused:
        _settings(environ)

    assert "may not read secret/app/payment-only" in str(refused.value)
    assert never_shown not in str(refused.value)


def test_a_missing_path_refuses_to_start(vault: DevVault, tmp_path: Path) -> None:
    environ = vault.role("shipping", ["app/shipping-service"], tmp_path)
    environ["VAULT_SECRET_PATHS"] = "app/shipping-service"

    with pytest.raises(VaultError, match="has no secret at secret/app/shipping-service"):
        _settings(environ)


def test_an_unreachable_vault_refuses_to_start(tmp_path: Path) -> None:
    (tmp_path / "r").write_text("role")
    (tmp_path / "s").write_text("secret")
    environ = {
        "VAULT_ADDR": f"http://127.0.0.1:{_free_port()}",
        "VAULT_ROLE_ID_FILE": str(tmp_path / "r"),
        "VAULT_SECRET_ID_FILE": str(tmp_path / "s"),
        "VAULT_SECRET_PATHS": "app/anything",
    }

    with pytest.raises(VaultError, match="unreachable"):
        _settings(environ)


def test_without_vault_configured_the_source_contributes_nothing() -> None:
    assert VaultSettingsSource(ServiceSettings, environ={})() == {}


def test_the_real_settings_read_vault_before_the_file() -> None:
    sources = Settings.settings_customise_sources(Settings, *(object(),) * 4)  # type: ignore[arg-type]
    assert isinstance(sources[2], VaultSettingsSource)


# ------------------------------------------------------------------- import


# A placeholder, never a key: the header is split so no literal private-key
# block appears in the repository for secret scanners to report.
PRIVATE_HEADER = "-----BEGIN " + "PRIVATE KEY-----"
PRIVATE_FOOTER = "-----END " + "PRIVATE KEY-----"

# Quoting styles the parser must handle: double quotes with spaces, bare, single quotes.
DATABASE_VALUE = _fake("value with spaces")
REDIS_VALUE, RABBIT_VALUE = _fake("redis"), _fake("rabbit")
STRIPE_VALUE, CJ_VALUE, VENDOR_VALUE = _fake("stripe"), _fake("cj"), _fake("vendor")

ENV_FILE = f"""# Local configuration
WEBSITE_NAME=Shop
POSTGRES_PASSWORD="{DATABASE_VALUE}"
REDIS_PASSWORD={REDIS_VALUE}
RABBITMQ_PASSWORD='{RABBIT_VALUE}'
USER_TOKEN_PRIVATE_KEY="{PRIVATE_HEADER}
MC4CAQAwBQYDK2VwBCIEIPLACEHOLDERPLACEHOLDERPLACEHOLDER
{PRIVATE_FOOTER}"
USER_TOKEN_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAPLACEHOLDER
-----END PUBLIC KEY-----"
STRIPE_TEST_SECRET_KEY={STRIPE_VALUE}
CJ_DROPSHIPPING_API_KEY={CJ_VALUE}
SOME_VENDOR_TOKEN={VENDOR_VALUE}
SECRET_ROLE=admin
"""


def _run_import(vault: DevVault, env_file: Path, *flags: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(IMPORT_SCRIPT), "--env-file", str(env_file), "--prefix", "imp", *flags],
        env={"VAULT_ADDR": vault.address, "VAULT_TOKEN": vault.root_token, "PATH": "/usr/bin:/bin"},
        capture_output=True, text=True, check=False,
    )


def test_a_dry_run_names_keys_only_and_changes_nothing(vault: DevVault, tmp_path: Path) -> None:
    env_file = tmp_path / "config"
    env_file.write_text(ENV_FILE)

    result = _run_import(vault, env_file, "--dry-run")

    assert result.returncode == 0, result.stderr
    assert "imp/shared-infra: POSTGRES_PASSWORD, RABBITMQ_PASSWORD, REDIS_PASSWORD" in result.stdout
    assert "SOME_VENDOR_TOKEN" in result.stdout  # flagged: looks secret, no Vault path
    assert REDIS_VALUE not in result.stdout and STRIPE_VALUE not in result.stdout
    assert env_file.read_text() == ENV_FILE


def test_the_import_moves_each_secret_to_its_service_and_keeps_the_rest(vault: DevVault, tmp_path: Path) -> None:
    env_file = tmp_path / "config"
    env_file.write_text(ENV_FILE)
    env_file.chmod(0o600)

    result = _run_import(vault, env_file)

    assert result.returncode == 0, result.stderr
    assert vault.get("imp/shared-infra") == {
        "POSTGRES_PASSWORD": DATABASE_VALUE, "REDIS_PASSWORD": REDIS_VALUE, "RABBITMQ_PASSWORD": RABBIT_VALUE,
    }
    assert vault.get("imp/user-service")["USER_TOKEN_PRIVATE_KEY"].count("\n") == 2  # multi-line PEM intact
    assert vault.get("imp/payment-service") == {"STRIPE_SECRET_KEY": STRIPE_VALUE}  # old name, new key
    assert vault.get("imp/supplier-service") == {"CJ_DROPSHIPPING_API_KEY": CJ_VALUE}

    left = env_file.read_text()
    for gone in ("POSTGRES_PASSWORD", "REDIS_PASSWORD", "USER_TOKEN_PRIVATE_KEY", "STRIPE_TEST_SECRET_KEY", "CJ_DROPSHIPPING_API_KEY"):
        assert gone not in left
    # Everything else is kept byte for byte, the public key's lines included.
    assert left.startswith("# Local configuration\nWEBSITE_NAME=Shop\n")
    assert 'USER_TOKEN_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEAPLACEHOLDER\n-----END PUBLIC KEY-----"\n' in left
    assert f"SOME_VENDOR_TOKEN={VENDOR_VALUE}\n" in left and "SECRET_ROLE=admin\n" in left
    assert env_file.stat().st_mode & 0o777 == 0o600


def test_a_second_import_keeps_what_vault_already_holds(vault: DevVault, tmp_path: Path) -> None:
    earlier, newer = _fake("earlier"), _fake("newer")
    extra = {"EXTRA": "kept"}
    vault.put("imp2/notification-service", {"MAIL_PASSWORD": earlier, **extra})
    env_file = tmp_path / "config"
    env_file.write_text(f"MAIL_PASSWORD={newer}\n")

    result = subprocess.run(
        [sys.executable, str(IMPORT_SCRIPT), "--env-file", str(env_file), "--prefix", "imp2"],
        env={"VAULT_ADDR": vault.address, "VAULT_TOKEN": vault.root_token, "PATH": "/usr/bin:/bin"},
        capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0, result.stderr
    assert vault.get("imp2/notification-service") == {"MAIL_PASSWORD": newer, **extra}
