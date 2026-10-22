"""A column that stores an email address encrypted and reads it back in plain text."""

from collections.abc import Callable

import sqlalchemy as sa
from sqlalchemy import String, event
from sqlalchemy.engine import Connection, Dialect
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql import operators
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.types import TypeDecorator

from infrastructure.utils.email_cipher import EmailCipher


class EncryptedColumnComparisonError(TypeError):
    """A comparison an encrypted column cannot answer."""


class EncryptedEmail(TypeDecorator[str]):
    """
    An email address stored encrypted (EmailCipher) and read back in plain text.

    The ciphertext is random, so the column itself can never be compared. A
    column declared with ``lookup`` names a column of the same table holding
    the address's keyed hash, and ``==`` / ``!=`` against an address become a
    comparison on that column. So ``get_by_field("email", ...)``, equality
    filters and the admin tables' filters find rows unchanged. Every other
    comparison (LIKE, IN, <, ...) would silently match nothing, so it raises.
    ``keep_lookup_in_step`` writes the hash whenever the address is set.

    Stored as a plain VARCHAR: migrations and ``alembic check`` see a String.
    """

    impl = String
    cache_ok = True

    # The longest stored form: a 320-character address in 4-byte UTF-8 (1,280
    # bytes) with its nonce and tag, base64url (1,744), after "e1.<key id>.".
    STORED_LENGTH = 2048
    LOOKUP_LENGTH = 64  # hex SHA-256

    def __init__(self, lookup: str | None = None) -> None:
        super().__init__(length=self.STORED_LENGTH)
        self.lookup: str | None = lookup

    @property
    def python_type(self) -> type[str]:
        # The admin tables coerce a filter value to its column's Python type.
        return str

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        return None if value is None else EmailCipher.current().encrypt(value)

    def process_result_value(self, value: str | None, dialect: Dialect) -> str | None:
        return None if value is None else EmailCipher.current().decrypt(value)

    class comparator_factory(TypeDecorator.Comparator[str]):
        _REFUSED = frozenset({
            operators.like_op, operators.not_like_op, operators.ilike_op, operators.not_ilike_op,
            operators.contains_op, operators.not_contains_op, operators.icontains_op, operators.not_icontains_op,
            operators.startswith_op, operators.not_startswith_op, operators.istartswith_op,
            operators.not_istartswith_op, operators.endswith_op, operators.not_endswith_op,
            operators.iendswith_op, operators.not_iendswith_op, operators.in_op, operators.not_in_op,
            operators.between_op, operators.not_between_op, operators.match_op, operators.not_match_op,
            operators.regexp_match_op, operators.not_regexp_match_op,
            operators.lt, operators.le, operators.gt, operators.ge,
        })

        def operate(self, op: Callable[..., ColumnElement[bool]], *other: object, **kwargs: object) -> ColumnElement[bool]:
            if op in (operators.eq, operators.ne) and other and other[0] is None:
                return super().operate(op, *other, **kwargs)  # IS NULL / IS NOT NULL
            if op in (operators.eq, operators.ne) and other and isinstance(other[0], str):
                return op(self._lookup_column(), EmailCipher.current().lookup_hash(other[0]))
            if op in (operators.eq, operators.ne) or op in self._REFUSED:
                raise EncryptedColumnComparisonError(
                    f"{self.expr} is encrypted: it can only be compared for equality with an address"
                )
            return super().operate(op, *other, **kwargs)

        def _lookup_column(self) -> ColumnElement[str]:
            lookup = self.type.lookup
            table = getattr(self.expr, "table", None)
            if lookup is None or table is None:
                raise EncryptedColumnComparisonError(f"{self.expr} is encrypted and has no lookup column")
            return table.c[lookup]

    @staticmethod
    def keep_lookup_in_step(attribute: InstrumentedAttribute[str] | InstrumentedAttribute[str | None]) -> None:
        """Set the attribute's lookup column whenever an address is assigned to it.

        Covers the constructor, setattr and the repositories' update methods,
        which all assign through the ORM; a bulk ``update()`` would bypass it.
        """
        column_type = attribute.property.columns[0].type
        if not isinstance(column_type, EncryptedEmail) or column_type.lookup is None:
            raise TypeError(f"{attribute} is not an EncryptedEmail column with a lookup")
        lookup = column_type.lookup

        @event.listens_for(attribute, "set")
        def _set_lookup(target: object, value: str | None, _old: object, _initiator: object) -> None:
            setattr(target, lookup, None if value is None else EmailCipher.current().lookup_hash(value))


class EncryptedEmailMigration:
    """
    Encrypts an existing plain-text email column in place, or decrypts it back.

    For the Alembic revision that turns a column into an EncryptedEmail: it
    reads and writes through plain columns, so the model's type is not
    involved, and skips rows already in the target form, so it can run again.
    """

    def __init__(self, connection: Connection, table: str, column: str,
                 lookup: str | None = None, key: str = "id", cipher: EmailCipher | None = None) -> None:
        self._connection = connection
        self._cipher = cipher or EmailCipher.current()
        self._column = column
        self._lookup = lookup
        text_columns = [column] + ([lookup] if lookup else [])
        # The key column is left untyped: asyncpg binds with an explicit cast,
        # and a UUID key compared with a VARCHAR parameter would fail.
        self._table = sa.table(table, sa.column(key), *(sa.column(name, String) for name in text_columns))
        self._key = self._table.c[key]

    def encrypt_rows(self) -> int:
        updates = [
            {"row_key": row_key, "value": self._cipher.encrypt(value)}
            | ({"lookup_value": self._cipher.lookup_hash(value)} if self._lookup else {})
            for row_key, value in self._rows()
            if not EmailCipher.is_encrypted(value)
        ]
        values = {self._column: sa.bindparam("value")}
        if self._lookup:
            values[self._lookup] = sa.bindparam("lookup_value")
        return self._update(updates, values)

    def decrypt_rows(self) -> int:
        updates = [
            {"row_key": row_key, "value": self._cipher.decrypt(value)}
            for row_key, value in self._rows()
            if EmailCipher.is_encrypted(value)
        ]
        return self._update(updates, {self._column: sa.bindparam("value")})

    def _rows(self) -> list[tuple[object, str]]:
        column = self._table.c[self._column]
        result = self._connection.execute(sa.select(self._key, column).where(column.is_not(None)))
        return [(row_key, value) for row_key, value in result]

    def _update(self, updates: list[dict[str, object]], values: dict[str, sa.BindParameter[str]]) -> int:
        if updates:
            self._connection.execute(
                sa.update(self._table).where(self._key == sa.bindparam("row_key")).values(values), updates
            )
        return len(updates)
