"""This service's copies of the cross-service wire contracts it publishes or consumes.

Every service keeps its own copy, trimmed to what it uses. Publishers add
fields only; consumers ignore fields they do not know (Pydantic's default),
and every event carries ``schema_version``. A change to an event lands in the
copy of every service that publishes or consumes it, in the same commit.
Values are bounded by ``limits`` (where a service carries it): a bound may
be raised at any time, but lowered only once no message still in a queue
or outbox can exceed it. ``backend/ci/check_copies.py`` fails when two
copies of a model differ.
"""
