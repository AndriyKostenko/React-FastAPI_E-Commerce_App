"""Settings source that loads a service's secrets from Vault at startup."""

import os
from collections.abc import Mapping

from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

from shared.vault.client import VaultClient, VaultConfig


class VaultSettingsSource(PydanticBaseSettingsSource):
    """
    This process's secrets from Vault, read once when the settings are built.

    Inactive (contributes nothing) when VAULT_ADDR is unset. When it is set,
    any failure to sign in or read raises VaultError, so the process refuses
    to start rather than run with secrets missing. Only keys that are settings
    fields are passed on.
    """

    def __init__(
        self,
        settings_cls: type[BaseSettings],
        environ: Mapping[str, str] | None = None,
        client: VaultClient | None = None,
    ) -> None:
        super().__init__(settings_cls)
        self._environ = os.environ if environ is None else environ
        self._client = client

    def __call__(self) -> dict[str, str]:
        client = self._client
        if client is None:
            config = VaultConfig.from_environment(self._environ)
            if config is None:
                return {}
            client = VaultClient(config)
        known = self._field_keys()
        return {key: value for key, value in client.read_all().items() if key in known}

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[None, str, bool]:
        # Values are produced in bulk by __call__; per-field lookup is unused.
        return None, field_name, False

    def _field_keys(self) -> set[str]:
        """Field names, plus every alias a field accepts (e.g. STRIPE_TEST_SECRET_KEY)."""
        keys: set[str] = set()
        for name, field in self.settings_cls.model_fields.items():
            keys.add(name)
            alias = field.validation_alias
            choices = getattr(alias, "choices", None)
            if isinstance(alias, str):
                keys.add(alias)
            elif choices:
                keys.update(choice for choice in choices if isinstance(choice, str))
        return keys
