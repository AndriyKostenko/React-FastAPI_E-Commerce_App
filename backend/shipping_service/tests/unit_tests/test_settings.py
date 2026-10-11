"""This service's own settings: secrets from Vault win over the config file."""

from settings import Settings
from infrastructure.vault import VaultSettingsSource


def test_settings_read_vault_before_the_config_file() -> None:
    sources = Settings.settings_customise_sources(Settings, *(object(),) * 4)  # type: ignore[arg-type]
    assert isinstance(sources[2], VaultSettingsSource)
