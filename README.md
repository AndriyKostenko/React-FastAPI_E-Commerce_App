## Getting Started

## Alembic migrations

- Initialize Alembic (if you haven’t): alembic init alembic

- Generate a new migration file: alembic revision --autogenerate -m "Your migration message"

- Review and clean up the migration: Check the generated file — remove redundant / incorrect staff or adjust logic as needed.

- Roll back a migration (optional): alembic downgrade -1 / alembic downgrade <revision_id>

- Mark current DB as up-to-date without running migrations: alembic stamp head (if got error about not matching your current models with existing, u can stamp specific idwith: alembic stamp <revision_id> )

## Redis

   Remember to:
      1. Cache only read operations
      2. Set appropriate expiration times
      3. Implement cache invalidation for write operations
      4. Monitor cache hit/miss rates
      5. Consider cache size and memory usage

   Redis docker container
   ` docker exec -it backend-redis-1 redis-cli ` : to check and interact with redis
 
   Auth in Redis
   ` AUTH your_redis_password`

   Select DB of Redis
   ` SELECT N ` 

   check keys in Redis
   ` KEYS * `  

   check value of the key
   ` GET <KEY>`

   Check if Redis is running
   ` sudo systemctl status redis `

   If not running, start it
   ` sudo systemctl start redis `

   ` sudo systemctl stop redis `

   Make sure Redis is enabled on startup
   `sudo systemctl enable redis`

   Find process using port 6379
   ` sudo lsof -i :6379 `

   Stop the process (if it's another Redis instance)
   `sudo systemctl stop redis-server`

## Docker
   building the image
   ` docker build -t user-service . `

   running with .env file
   ` docker run --env-file .env user-service ` 

   ` docker compose up --build`

   ` docker compose restart <service-name> `

   Stop containers and remove volumes
   ` docker compose down -v `

   Remove the DB volume (WARNING: deletes all Postgres data!)
   ` docker volume rm backend_postgres_data `

   Remove all existing containers, networks, and volumes
   ` docker system prune -af --volumes `

## UV

 - uv init
 - uv venv
 - source .venv/bin/activate
 - uv add <package_name>
 - uv lock
 - uv pip list



## FastStream (RabbitMQ)
User Action → API Gateway → User Service → Response
                ↓
          Publish Event → RabbitMQ Queue
                ↓
       Notification Service → Send Email


Event Flow Summary:

User Registration: API Gateway → User Service → Event → Notification Consumer
Password Reset Request: API Gateway → User Service → Event → Notification Consumer
Email Verification: API Gateway → Event → Notification Consumer
Direct Email Endpoints: For testing/admin purposes only




## PG Admin
   - http://localhost:5050