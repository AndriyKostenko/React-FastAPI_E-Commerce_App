
from shared.email_service import EmailService
from shared.logger_config import setup_logger
from shared.redis_manager import RedisManager
from shared.settings import get_settings
from shared.database_setup import DatabaseSessionManager
from shared.authentication import AuthenticationManager


# Initialize settings
settings = get_settings()

# Logger setup
logger = setup_logger(__name__)

# Email Service
email_service = EmailService(settings=settings, logger=logger)

# Authentication Manager
auth_manager = AuthenticationManager(settings_instance=settings)



#-----------------------------------Redis-Managers------------------------------------------------

# Redis managers for each service
api_gateway_redis_manager = RedisManager(service_prefix="api-gateway", 
                                         redis_url=settings.APIGATEWAY_SERVICE_REDIS_URL,
                                         logger=logger,
                                         service_api_version=settings.API_GATEWAY_SERVICE_URL_API_VERSION)
user_service_redis_manager = RedisManager(service_prefix="user-service", 
                                          redis_url=settings.USER_SERVICE_REDIS_URL,
                                          logger=logger,
                                          service_api_version=settings.USER_SERVICE_URL_API_VERSION,)
product_service_redis_manager = RedisManager(service_prefix="product-service", 
                                             redis_url=settings.PRODUCT_SERVICE_REDIS_URL,
                                             logger=logger,
                                             service_api_version=settings.PRODUCT_SERVICE_URL_API_VERSION,)
notification_service_redis_manager = RedisManager(service_prefix="notification-service",
                                                  redis_url=settings.NOTIFICATION_SERVICE_REDIS_URL,
                                                  logger=logger,
                                                  service_api_version=settings.NOTIFICATION_SERVICE_URL_API_VERSION,)



#------------------------------------DB-Managers-----------------------------------------------

# Database session managers for each service
user_service_database_session_manager = DatabaseSessionManager(
    database_url=settings.USER_SERVICE_DATABASE_URL, 
    engine_settings={"echo": True,  # Set to True in develpment for logging SQL queries
                     "pool_pre_ping": True,  # If True, the connection pool will check for stale connections and refresh them.
                     "pool_size": 100, # The maximum number of database connections to pool
                     "max_overflow": 0, #The maximum number of connections to allow in the connection pool above pool_size. It's set to 0, meaning no overflow connections are allowed.
                    },
    logger=logger
)

product_service_database_session_manager = DatabaseSessionManager(
    database_url=settings.PRODUCT_SERVICE_DATABASE_URL,
    engine_settings={"echo": True,  # Set to True in develpment for logging SQL queries
                     "pool_pre_ping": True,  # If True, the connection pool will check for stale connections and refresh them.
                     "pool_size": 100, # The maximum number of database connections to pool
                     "max_overflow": 0, #The maximum number of connections to allow in the connection pool above pool_size. It's set to 0, meaning no overflow connections are allowed.
                    },
    logger=logger
)

notification_service_database_session_manager = DatabaseSessionManager(
    database_url=settings.NOTIFICATION_SERVICE_DATABASE_URL,
    engine_settings={"echo": True,  # Set to True in develpment for logging SQL queries
                     "pool_pre_ping": True,  # If True, the connection pool will check for stale connections and refresh them.
                     "pool_size": 100, # The maximum number of database connections to pool
                     "max_overflow": 0, #The maximum number of connections to allow in the connection pool above pool_size. It's set to 0, meaning no overflow connections are allowed.
                    },
    logger=logger
)

