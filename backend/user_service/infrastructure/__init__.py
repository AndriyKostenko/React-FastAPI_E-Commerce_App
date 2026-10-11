"""This service's own copy of the infrastructure every service is built on.

App builder, middleware, auth, messaging, database, outbox, resilience, Vault
and the test helpers. The other services carry the same modules under the same
paths (each only those it uses), so two copies compare with ``diff -r``. There
is no shared library: a fix to one of these modules goes into every copy.
"""
