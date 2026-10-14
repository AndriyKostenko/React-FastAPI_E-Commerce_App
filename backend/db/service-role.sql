-- Give one service its own Postgres login and make it the owner of the
-- database this runs in (its <service>_db or <service>_test_db).
--
-- Run as a superuser, connected to that database, with two psql variables:
--   role      the login, named after the service directory (e.g. supplier_service)
--   password  its password, [A-Za-z0-9] only
-- Pass them on stdin (\set lines ahead of this file), never as -v arguments,
-- which would show the password in the process list. Both local/dev.sh and
-- ci/prepare.sh run it; it is safe to run again (it also resets the password).
--
-- The login owns the database and every object in its public schema, so its
-- migrations run as it; it holds no other privilege (not a superuser, cannot
-- create databases or roles), and no other login may connect to the database.

\set ON_ERROR_STOP on

SELECT NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'role') AS role_missing \gset
\if :role_missing
  CREATE ROLE :"role" LOGIN;
\endif
ALTER ROLE :"role" WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
  PASSWORD :'password';

ALTER DATABASE :"DBNAME" OWNER TO :"role";
-- Owner first, then the revoke: the ACL is rebuilt around the new owner, who
-- keeps CONNECT; PUBLIC (every other login) loses CONNECT and TEMPORARY.
REVOKE ALL ON DATABASE :"DBNAME" FROM PUBLIC;
-- Nor may a service login open the maintenance databases, which every login
-- can by default. Only the superuser uses them, and it bypasses this.
REVOKE ALL ON DATABASE postgres, template1 FROM PUBLIC;

-- Objects the superuser created (every migration so far ran as it) move to
-- the service login. REASSIGN OWNED cannot be used: the bootstrap superuser
-- also owns the system catalogs. A psql variable does not reach inside a DO
-- body, so the role travels as a session setting.
SELECT set_config('ecommerce.service_role', :'role', false) AS service_role \gset
DO $$
DECLARE
  target text := current_setting('ecommerce.service_role');
  item record;
BEGIN
  -- Tables, views, materialized views and free-standing sequences. A table's
  -- indexes and its serial/identity sequences follow the table and cannot be
  -- moved on their own, so they are skipped here.
  FOR item IN
    SELECT c.relname,
           CASE c.relkind WHEN 'v' THEN 'VIEW' WHEN 'm' THEN 'MATERIALIZED VIEW'
                          WHEN 'S' THEN 'SEQUENCE' ELSE 'TABLE' END AS kind
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public'
       AND c.relkind IN ('r', 'p', 'v', 'm', 'S')
       AND pg_get_userbyid(c.relowner) <> target
       AND NOT (c.relkind = 'S' AND EXISTS (
             SELECT 1 FROM pg_depend d
              WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid AND d.deptype IN ('a', 'i')))
     ORDER BY c.relkind DESC  -- 'r'/'p' before 'S': tables first
  LOOP
    EXECUTE format('ALTER %s public.%I OWNER TO %I', item.kind, item.relname, target);
  END LOOP;

  -- Enum and domain types (Alembic creates the enums). Composite types of
  -- tables and array types follow their table or element type.
  FOR item IN
    SELECT t.typname, CASE t.typtype WHEN 'd' THEN 'DOMAIN' ELSE 'TYPE' END AS kind
      FROM pg_type t
      JOIN pg_namespace n ON n.oid = t.typnamespace
     WHERE n.nspname = 'public'
       AND t.typtype IN ('e', 'd')
       AND pg_get_userbyid(t.typowner) <> target
  LOOP
    EXECUTE format('ALTER %s public.%I OWNER TO %I', item.kind, item.typname, target);
  END LOOP;

  -- Functions and procedures (none today; here so a future one is not missed).
  FOR item IN
    SELECT p.oid::regprocedure::text AS signature
      FROM pg_proc p
      JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'public'
       AND pg_get_userbyid(p.proowner) <> target
  LOOP
    EXECUTE format('ALTER ROUTINE %s OWNER TO %I', item.signature, target);
  END LOOP;
END
$$;
