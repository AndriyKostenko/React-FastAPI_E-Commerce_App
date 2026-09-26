"""Stripe Tax: calculating sales tax, then recording what was actually collected.

Two jobs, two classes:

- ``TaxCalculationService`` prices the tax on an order before it is placed.
  The Stripe Tax Calculation it creates is stored with the order and the
  payment; it records nothing for filing yet.
- ``PaymentTaxLedger`` records the tax filing entries once money moves: a
  sale transaction when the card is captured, and a flat-amount reversal for
  every amount given back (a pre-capture reduction or a refund).

The "simplified" Stripe integration (linking the calculation to the
PaymentIntent) is deliberately not used: it records the full calculated tax
even when less is captured, and this service captures less whenever lines are
refunded before capture.
"""

from logging import Logger
from typing import Any

import stripe
from stripe import StripeClient, StripeError

from models.payment_models import Payment
from shared.contracts.tax import TaxCalculationRequest, TaxCalculationResult
from shared.exceptions.base_exceptions import BaseAPIException
from shared.settings import Settings


class TaxLocationInvalidError(BaseAPIException):
    """Stripe cannot place the address precisely enough to tax it."""

    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            detail="The shipping address is not precise enough to calculate tax; please check it",
        )


class TaxCalculationError(BaseAPIException):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=502, detail=f"Tax could not be calculated: {detail}")


class TaxCalculationService:
    def __init__(self, stripe_client: StripeClient, settings: Settings) -> None:
        self._stripe = stripe_client
        self._settings = settings

    async def calculate(self, request: TaxCalculationRequest) -> TaxCalculationResult:
        try:
            calculation = await self._stripe.v1.tax.calculations.create_async(self._params(request))
        except stripe.InvalidRequestError as error:
            if error.code == "customer_tax_location_invalid":
                raise TaxLocationInvalidError() from error
            raise TaxCalculationError(error.user_message or str(error)) from error
        except StripeError as error:
            raise TaxCalculationError(str(error)) from error
        return TaxCalculationResult(
            calculation_id=calculation.id,
            tax_cents=calculation.tax_amount_exclusive,
            total_cents=calculation.amount_total,
        )

    def _params(self, request: TaxCalculationRequest) -> dict[str, Any]:
        tax_code = self._settings.STRIPE_TAX_PRODUCT_TAX_CODE
        line_items: list[dict[str, Any]] = []
        for line in request.lines:
            item: dict[str, Any] = {
                "amount": line.amount_cents,
                "quantity": line.quantity,
                "reference": line.reference,
                # Our prices never include tax: it is added on top.
                "tax_behavior": "exclusive",
            }
            if tax_code:
                item["tax_code"] = tax_code
            line_items.append(item)

        # Stripe rejects empty strings, so only the address parts we have go in.
        address = {
            key: value
            for key, value in request.address.model_dump().items()
            if value
        }
        params: dict[str, Any] = {
            "currency": request.currency.lower(),
            "line_items": line_items,
            "customer_details": {"address": address, "address_source": "shipping"},
        }
        if request.shipping_cents:
            params["shipping_cost"] = {"amount": request.shipping_cents}
        return params


class PaymentTaxLedger:
    """
    Records the tax filing entries for a payment on Stripe.

    Money has already moved when these run, so they never raise: a failure is
    logged as critical for an operator to record by hand, rather than undoing
    or retrying a capture or refund. Idempotency keys make a repeated call
    return the entry already created.
    """

    def __init__(self, stripe_client: StripeClient, logger: Logger) -> None:
        self._stripe = stripe_client
        self._logger = logger

    async def record_sale(self, payment: Payment) -> str | None:
        """Tax transaction id for a captured payment, created on first call."""
        if payment.tax_calculation_id is None:
            return None  # untaxed order: tax was off when it was placed
        if payment.tax_transaction_id is not None:
            return payment.tax_transaction_id
        try:
            transaction = await self._stripe.v1.tax.transactions.create_from_calculation_async(
                {
                    "calculation": payment.tax_calculation_id,
                    # Shown in Stripe's tax exports: reconciles back to the order.
                    "reference": f"order_{payment.order_id}",
                },
                options={"idempotency_key": f"tax_transaction:sale:{payment.order_id}"},
            )
        except StripeError as error:
            self._logger.critical(
                "TAX RECORD REQUIRED for order %s: the sale could not be recorded "
                "from calculation %s: %s",
                payment.order_id, payment.tax_calculation_id, error,
            )
            return None
        return transaction.id

    async def record_reversal(
        self, payment: Payment, transaction_id: str, *, reference: str, amount_cents: int
    ) -> None:
        """
        Record ``amount_cents`` (tax included) given back to the customer.

        Stripe spreads a flat amount over the lines and shipping in proportion
        to what is left on each, which matches how order-service adds the
        refunded lines' share of the tax to a refund.
        """
        if amount_cents <= 0:
            return
        try:
            await self._stripe.v1.tax.transactions.create_reversal_async(
                {
                    "mode": "partial",
                    "original_transaction": transaction_id,
                    "reference": reference,
                    "flat_amount": -amount_cents,
                },
                options={"idempotency_key": f"tax_transaction:reversal:{reference}"},
            )
        except StripeError as error:
            self._logger.critical(
                "TAX RECORD REQUIRED for order %s: a reversal of %s cents (%s) "
                "could not be recorded against %s: %s",
                payment.order_id, amount_cents, reference, transaction_id, error,
            )
