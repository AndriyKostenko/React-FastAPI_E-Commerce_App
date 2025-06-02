## Getting Started

## Alembic migrations

- Initialize Alembic (if you haven’t): alembic init alembic

- Generate a new migration file: alembic revision --autogenerate -m "Your migration message"

- Review and clean up the migration: Check the generated file — remove redundant / incorrect staff or adjust logic as needed.

- Roll back a migration (optional): alembic downgrade -1 / alembic downgrade <revision_id>

- Mark current DB as up-to-date without running migrations: alembic stamp head (if got error about not matching your current models with existing, u can stamp specific idwith: alembic stamp <revision_id> )

## Redis
 - redis-cli : to check and interact with redis
 - redis-cli
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