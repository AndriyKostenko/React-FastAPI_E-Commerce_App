"""The settings shared/'s own test suite runs with.

shared/'s modules read the running service's own top-level ``settings``
module, which each service provides. This one stands in for it while shared/'s
suite runs, holding only what those tests read. It goes once the modules and
their tests move into the services (PRODUCTION_GAPS §8.5, phase 4).
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from shared.vault import VaultSettingsSource

# backend/'s config file, as in every service's settings.
_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config: SettingsConfigDict = SettingsConfigDict(
        env_file=_ROOT_ENV,
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings, env_settings, VaultSettingsSource(settings_cls), dotenv_settings, file_secret_settings)

    RABBITMQ_HOST: str
    RABBITMQ_PORT: int
    RABBITMQ_USER: str
    RABBITMQ_PASSWORD: str

    @property
    def RABBITMQ_BROKER_URL(self) -> str:
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}"


class TestSettings(BaseSettings):
    """Nothing in shared/'s suite reads test settings; the type is imported only."""


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_test_settings() -> TestSettings:
    return TestSettings()
