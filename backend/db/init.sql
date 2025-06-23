-- Drop databases if they exist
DROP DATABASE IF EXISTS product_service_db;
DROP DATABASE IF EXISTS user_service_db;

-- Create databases
CREATE DATABASE product_service_db
    WITH
    OWNER = postgres
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.utf8'
    LC_CTYPE = 'en_US.utf8';

CREATE DATABASE user_service_db
    WITH
    OWNER = postgres
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.utf8'
    LC_CTYPE = 'en_US.utf8';