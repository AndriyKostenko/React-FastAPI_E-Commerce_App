"""This service's copies of the cross-service wire contracts it publishes or consumes.

Every service keeps its own copy, trimmed to what it uses. Publishers add
fields only; consumers ignore fields they do not know (Pydantic's default),
and every event carries ``schema_version``. A change to an event lands in the
copy of every service that publishes or consumes it, in the same commit.
"""
