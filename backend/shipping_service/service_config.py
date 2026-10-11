from logging import Logger

from infrastructure.managers.logger_manager import setup_logger
from settings import Settings, get_settings


settings: Settings = get_settings()
logger: Logger = setup_logger("shipping-service")
