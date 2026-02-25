-- Create databases for each microservice
CREATE DATABASE user_service_db;
CREATE DATABASE user_service_test_db;
CREATE DATABASE product_service_db;
CREATE DATABASE product_service_test_db;
CREATE DATABASE notification_service_db;
CREATE DATABASE notification_service_test_db;
CREATE DATABASE order_service_db;
CREATE DATABASE order_service_test_db;
CREATE DATABASE outbox_events_db;
CREATE DATABASE outbox_events_test_db;


-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE user_service_db TO postgres;
GRANT ALL PRIVILEGES ON DATABASE user_service_test_db TO postgres;
GRANT ALL PRIVILEGES ON DATABASE product_service_db TO postgres;
GRANT ALL PRIVILEGES ON DATABASE product_service_test_db TO postgres;
GRANT ALL PRIVILEGES ON DATABASE notification_service_db TO postgres;
GRANT ALL PRIVILEGES ON DATABASE notification_service_test_db TO postgres;
GRANT ALL PRIVILEGES ON DATABASE order_service_db TO postgres;
GRANT ALL PRIVILEGES ON DATABASE order_service_test_db TO postgres;
GRANT ALL PRIVILEGES ON DATABASE outbox_events_db TO postgres;
GRANT ALL PRIVILEGES ON DATABASE outbox_events_test_db TO postgres;
