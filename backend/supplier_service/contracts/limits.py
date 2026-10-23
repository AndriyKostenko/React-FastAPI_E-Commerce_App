"""
Upper bounds on what crosses a service's edge: API inputs and event payloads.

Every service that bounds its schemas carries this same file (``diff`` the
copies), so a value one service publishes is one every consumer accepts. The
bounds sit well above real data (the catalogue on 2026-10-21: longest product
name 137 characters, variant name 151, image URL 103; at most 120 variants and
30 images on one product). They stop a caller, or a damaged message, from
pushing an unbounded value through; a schema narrows them where a field has a
rule of its own (a name of 2-50 characters, a quantity of at most 99).

API inputs over a bound are refused (422). On events, free text is clipped
instead (``ClippedText``): a reason or an error message is built from whatever
failed, and an over-long one must not stop the event, and the saga step that
publishes it, from going out. Raise a bound freely; lower one only once no
message in a queue or outbox can still exceed it.
"""

from decimal import Decimal
from typing import Annotated

from pydantic import BeforeValidator, Field, StringConstraints


# ------------------------------------------------------------------ strings

# Statuses, event and service names, currencies, ISO, province and colour codes.
CODE_MAX_LENGTH: int = 64
# Ids another system issues: Stripe, CJ (pid, vid, order number), SKUs,
# barcodes, tracking numbers, supplier and category ids.
IDENTIFIER_MAX_LENGTH: int = 255
# Product, variant, category, carrier and logistics names.
NAME_MAX_LENGTH: int = 500
# URLs and storage keys.
URL_MAX_LENGTH: int = 2048
# Opaque credentials: JWTs, Google ID tokens, Turnstile and reset tokens.
TOKEN_MAX_LENGTH: int = 4096
# What people write: notes, reasons, review and return descriptions.
TEXT_MAX_LENGTH: int = 5000
# A supplier's own product description: HTML, cleaned up by product-service.
SUPPLIER_TEXT_MAX_LENGTH: int = 100_000

# ------------------------------------------------------------------ numbers

# Units on one cart or order line, as the storefront allows.
LINE_QUANTITY_MAX: int = 99
# Any other count: stock, units sold, batch numbers, results.
COUNT_MAX: int = 1_000_000_000
# Any one amount of money, in whatever currency the field names.
MONEY_MAX: Decimal = Decimal("1000000")
# MONEY_MAX in minor units.
CENTS_MAX: int = 100_000_000

# -------------------------------------------------------------- collections

# Lines of one cart, order, refund or return.
LINES_MAX: int = 50
# Variants of one product.
VARIANTS_MAX: int = 1000
# Images of one product.
IMAGES_MAX: int = 100
# Names of a product's variant options ("Color", "Size").
OPTION_NAMES_MAX: int = 5
# Products or stock levels in one supplier event, and the errors about them.
BATCH_MAX: int = 1000
# Keys of a free-form JSON object (a variant snapshot, a supplier config).
OBJECT_KEYS_MAX: int = 100


def _clipped_to(max_length: int) -> BeforeValidator:
    """Cuts a string to ``max_length`` characters; anything else is left to the type check."""

    def clip(value: object) -> object:
        return value[:max_length] if isinstance(value, str) else value

    return BeforeValidator(clip)


Code = Annotated[str, StringConstraints(max_length=CODE_MAX_LENGTH)]
Identifier = Annotated[str, StringConstraints(max_length=IDENTIFIER_MAX_LENGTH)]
Name = Annotated[str, StringConstraints(max_length=NAME_MAX_LENGTH)]
Url = Annotated[str, StringConstraints(max_length=URL_MAX_LENGTH)]
Token = Annotated[str, StringConstraints(max_length=TOKEN_MAX_LENGTH)]
Text = Annotated[str, StringConstraints(max_length=TEXT_MAX_LENGTH)]
# Free text on an event: clipped, never refused (see the module docstring).
ClippedText = Annotated[str, _clipped_to(TEXT_MAX_LENGTH)]
SupplierText = Annotated[str, _clipped_to(SUPPLIER_TEXT_MAX_LENGTH)]

LineQuantity = Annotated[int, Field(gt=0, le=LINE_QUANTITY_MAX)]
Count = Annotated[int, Field(ge=0, le=COUNT_MAX)]
PositiveCount = Annotated[int, Field(gt=0, le=COUNT_MAX)]
Cents = Annotated[int, Field(ge=0, le=CENTS_MAX)]
Money = Annotated[Decimal, Field(ge=0, le=MONEY_MAX)]
