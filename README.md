## Getting Started

## Alembic migrations

- Initialize Alembic (if you haven’t): alembic init alembic

- Generate a new migration file: alembic revision --autogenerate -m "Your migration message"

- Review and clean up the migration: Check the generated file — remove redundant / incorrect staff or adjust logic as needed.

- Roll back a migration (optional): alembic downgrade -1 / alembic downgrade <revision_id>

- Mark current DB as up-to-date without running migrations: alembic stamp head (if got error about not matching your current models with existing, u can stamp specific idwith: alembic stamp <revision_id> )
