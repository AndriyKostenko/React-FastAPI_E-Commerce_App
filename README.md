## Getting Started

## Alembic migrations

- Initialize Alembic (if you haven’t): alembic init alembic

- Generate a new migration file: alembic revision --autogenerate -m "Your migration message"

- Review and clean up the migration: Check the generated file — remove redundant / incorrect staff or adjust logic as needed.

- Roll back a migration (optional): alembic downgrade -1 / alembic downgrade <revision_id>

- Mark current DB as up-to-date without running migrations: alembic stamp head (if got error about not matching your current models with existing, u can stamp specific idwith: alembic stamp <revision_id> )

## Redis
 - docker exec -it backend-redis-1 redis-cli : to check and interact with redis
 - 
    KEYS *    : check keys in Redis

   Remember to:
   1. Cache only read operations
   2. Set appropriate expiration times
   3. Implement cache invalidation for write operations
   4. Monitor cache hit/miss rates
   5. Consider cache size and memory usage

   # Check if Redis is running
   sudo systemctl status redis

   # If not running, start it
   sudo systemctl start redis

   # Make sure Redis is enabled on startup
   sudo systemctl enable redis

   # Find process using port 6379
   sudo lsof -i :6379

   # Stop the process (if it's another Redis instance)
   sudo systemctl stop redis-server

## Docker
   - docker build -t user-service . : (building the image)
   - docker run --env-file .env user-service : (running with .env file)
   - docker compose up --build
   - docker compose down
   - docker volume rm backend_postgres_data (Remove the DB volume (WARNING: deletes all Postgres data!))

## UV
 
 - uv venv : creating virtual env
 - source .venv/bin/activate
 - uv pip install -r requirements.txt
 - uv pip install <package name>


## PG Admin
   - http://localhost:5050