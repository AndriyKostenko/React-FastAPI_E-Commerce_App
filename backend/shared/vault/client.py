"""A minimal HashiCorp Vault client: AppRole sign-in and KV v2 reads.

Each service signs in with its own AppRole, whose policy lets it read only its
own secret path (plus the infrastructure credentials every process needs), so
a compromised process can read nothing beyond what it already holds.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import httpx


class VaultError(RuntimeError):
    """Vault is configured for this process but its secrets could not be loaded.

    Raised at startup, so the process refuses to run instead of starting with
    secrets missing. Messages name the address and path, never a secret value.
    """


@dataclass(frozen=True, slots=True)
class VaultConfig:
    """Where this process's secrets are and how it signs in to read them."""

    address: str
    role_id: str
    secret_id: str
    # Read in order; a key in a later path overrides the same key in an earlier one.
    secret_paths: tuple[str, ...]
    kv_mount: str = "secret"
    timeout_seconds: float = 5.0

    ADDRESS_VARIABLE = "VAULT_ADDR"

    @classmethod
    def from_environment(cls, environ: Mapping[str, str]) -> "VaultConfig | None":
        """The configuration dev.sh (or a deployment) hands the process; None when Vault is not in use."""
        address = environ.get(cls.ADDRESS_VARIABLE, "").strip()
        if not address:
            return None
        paths = tuple(part.strip() for part in environ.get("VAULT_SECRET_PATHS", "").split(",") if part.strip())
        if not paths:
            raise VaultError(f"{cls.ADDRESS_VARIABLE} is set but VAULT_SECRET_PATHS names no secret path")
        return cls(
            address=address.rstrip("/"),
            role_id=_read_credential(environ, "VAULT_ROLE_ID_FILE"),
            secret_id=_read_credential(environ, "VAULT_SECRET_ID_FILE"),
            secret_paths=paths,
            kv_mount=environ.get("VAULT_KV_MOUNT", "secret").strip() or "secret",
        )


def _read_credential(environ: Mapping[str, str], variable: str) -> str:
    """AppRole credentials come from files (mode 600), not from the environment itself."""
    location = environ.get(variable, "").strip()
    if not location:
        raise VaultError(f"VAULT_ADDR is set but {variable} is not")
    try:
        value = Path(location).read_text().strip()
    except OSError as error:
        raise VaultError(f"{variable} points at {location}, which cannot be read: {error.strerror}") from error
    if not value:
        raise VaultError(f"{variable} points at {location}, which is empty")
    return value


class VaultClient:
    """Signs in with an AppRole and reads KV v2 secrets."""

    def __init__(self, config: VaultConfig, http: httpx.Client | None = None) -> None:
        self._config = config
        self._http = http or httpx.Client(base_url=config.address, timeout=config.timeout_seconds)
        self._token: str | None = None

    def read_all(self) -> dict[str, str]:
        """Every key from every configured path, later paths winning on a clash."""
        values: dict[str, str] = {}
        for path in self._config.secret_paths:
            values.update(self.read(path))
        return values

    def read(self, path: str) -> dict[str, str]:
        response = self._request("GET", f"/v1/{self._config.kv_mount}/data/{path}", token=self._login())
        if response.status_code == 404:
            raise VaultError(f"Vault at {self._config.address} has no secret at {self._config.kv_mount}/{path}")
        if response.status_code == 403:
            raise VaultError(f"This process's Vault role may not read {self._config.kv_mount}/{path}")
        self._raise_for(response, f"reading {self._config.kv_mount}/{path}")
        data = ((response.json().get("data") or {}).get("data")) or {}
        return {str(key): str(value) for key, value in data.items()}

    def _login(self) -> str:
        if self._token is None:
            response = self._request(
                "POST",
                "/v1/auth/approle/login",
                json={"role_id": self._config.role_id, "secret_id": self._config.secret_id},
            )
            self._raise_for(response, "signing in with this service's AppRole")
            self._token = str(response.json()["auth"]["client_token"])
        return self._token

    def _request(
        self, method: str, url: str, *, token: str | None = None, json: dict[str, str] | None = None
    ) -> httpx.Response:
        headers = {"X-Vault-Token": token} if token else {}
        try:
            return self._http.request(method, url, headers=headers, json=json)
        except httpx.HTTPError as error:
            raise VaultError(f"Vault at {self._config.address} is unreachable: {error}") from error

    def _raise_for(self, response: httpx.Response, action: str) -> None:
        if response.is_success:
            return
        if response.status_code == 503:
            raise VaultError(f"Vault at {self._config.address} is sealed or not initialised ({action})")
        # Vault's error bodies describe the request, never the secret.
        raise VaultError(f"Vault refused {action}: HTTP {response.status_code} {response.text[:200]}")
