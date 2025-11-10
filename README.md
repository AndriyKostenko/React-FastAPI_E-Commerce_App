## Getting Started




## Alembic migrations

- Initialize Alembic (if you haven’t): 
 `alembic init alembic`

- Generate a new migration file: 
  `alembic revision --autogenerate -m "Your migration message"`

- Review and clean up the migration: Check the generated file — remove redundant / incorrect staff or adjust logic as needed.

- Roll back a migration (optional): 
  `alembic downgrade -1 / alembic downgrade <revision_id>`

- Mark current DB as up-to-date without running migrations: 
  ` alembic stamp head` (if got error about not matching your current models with existing, u can stamp specific idwith: alembic stamp <revision_id> )

- To apply alembic migrations u neeed first to go to the container, then activate venv, then aplly migrations: 
    `docker compose exec user-service bash`
    `source .venv/bin/activate`
    # Review the migration file before running!
    `cat alembic/versions/<new_file>.py`
    # If it looks correct (no DROP TABLE), run:
    `alembic upgrade head`    



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






## UV

 - uv init
 - uv venv
 - source .venv/bin/activate
 - uv add <package_name>
 - uv lock
 - uv pip list



## FastStream (RabbitMQ)

   RabbitMQ url
   `http://localhost:15672`

   FastStream allows you to scale application right from the command line by running you application in the Process pool.
   ` faststream run serve:app --workers 2 `

   Generating of ApiDocs
   1. ` docker compose ps ` - checking all running services
   2. ` docker compose exec notification-consumer sh ` - entering the container
   3. ` faststream docs serve main:app --host 0.0.0.0 --port 8004 ` - generatig the
   4. ` http://0.0.0.0:8004/docs/asyncapi ` - opening generated docs

   Once confirmed, open your browser and go to:
   http://localhost:15672
   You'll see the RabbitMQ Management interface where you can:

   View Exchanges (where messages are published)
   View Queues (where messages are stored)
   View Connections (active connections)
   Monitor Message rates
   Debug Message flow


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




## Typical target latency budgets (containerized microservices, single region, moderate load):

P50, P95, P99 are latency percentiles.

P50 (50th percentile): Median. 50% of requests are faster than this value, 50% slower.
P95 (95th percentile): 95% of requests complete at or below this time; 5% are slower.
P99 (99th percentile): Tail latency. Only 1% of requests are slower. Shows rare slow cases.

Login (/login):

P50: 80–150 ms
P95: <300 ms
P99: <500 ms Dominant cost: password hash verify (bcrypt 12 cost ~80–200 ms). Acceptable: your 200 ms is fine.
Register (/register):

P50: 120–250 ms (DB insert + token generation)
P95: <600 ms
P99: <900 ms Send email asynchronously (queue) so request isn’t blocked by SMTP/API (email call alone can be 150–400 ms).
Password reset request (/password-reset/request):

P50: 100–180 ms (create token + persist)
P95: <350–400 ms Offload email same as register.
Password reset confirm (/password-reset/confirm):

P50: 90–170 ms (verify token + hash new password + update)
P95: <350 ms
P99: <550 ms
Access token refresh (/refresh):

P50: 40–90 ms
P95: <180 ms
Simple authenticated GET (user profile):

P50: 30–70 ms
P95: <150 ms
List endpoints (small result sets):

P50: 40–90 ms
P95: <180 ms
Write operations (standard DB insert/update):

P50: 50–120 ms
P95: <250 ms
SLO suggestions:

Global: 99% of auth-related requests <500 ms
P95 login/register <300–400 ms
Error rate <0.1%
If you need tighter login times:

Reduce bcrypt rounds (only if policy allows) or switch to Argon2id tuned for ~100 ms
Warm containers (avoid CPU throttling)
Trim excessive synchronous logging
Reuse DB sessions and HTTP clients


## AdminJS

------




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

   Quick one-liner to remove only <none> images:
   ` docker rmi $(docker images -f "dangling=true" -q)`

   rebuild via docker compose
   `docker compose build <service-name> --no-cache`
   
   restart via docker compose sepc. service
   `docker compose up <service-name>`

   Stop the service:
   `docker compose stop user-service`

   Rebuild with updated code:
   `docker compose build user-service`

   Start it again (detached):
   `docker compose up -d user-service`