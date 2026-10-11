from logging import Logger

from shared.managers.logger_manager import setup_logger
from settings import Settings, get_settings


settings: Settings = get_settings()
logger: Logger = setup_logger("cart-service")
