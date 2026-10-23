"""A VARCHAR(n) column that cuts what it is given to n characters instead of failing the write."""

from sqlalchemy import String
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


class ClippedString(TypeDecorator[str]):
    """
    For text a service writes from whatever happened: an error message, a reason
    taken from an event. Such text has no length of its own, and an over-long
    one must not lose the row it belongs to (a failed payment, a cancelled
    order), so it is clipped. Text a person types is bounded by its request
    schema instead, and refused there.

    Stored as a plain VARCHAR(n): migrations and ``alembic check`` see a String.
    """

    impl = String
    cache_ok = True

    def __init__(self, length: int) -> None:
        super().__init__(length=length)
        self.length: int = length

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        return value[: self.length] if isinstance(value, str) else value
