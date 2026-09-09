"""Builds the paper that travels in the box with an in-house printed garment."""

from datetime import UTC, datetime

from models.order_fulfillment_models import CustomProductionJob
from schemas.production_schemas import (
    PackingSlipAddress,
    PackingSlipLine,
    PackingSlipSchema,
    PrintSpecification,
)
from shared.contracts.order import CustomTshirtSpecification
from shared.settings import Settings


class PackingSlipBuilder:
    """Assembles a printable packing slip from one production job.

    The slip is returned as structured data rather than a rendered document so
    the admin UI can lay it out and print it, and so the API gateway — which
    normalizes every upstream response to JSON — can carry it unchanged.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

    def build(self, job: CustomProductionJob) -> PackingSlipSchema:
        order = job.order
        address = order.address
        specification = self.parse_specification(job)

        return PackingSlipSchema(
            job_id=job.id,
            order_id=order.id,
            order_placed_at=order.date_created,
            issued_at=datetime.now(UTC),
            customer_email=order.user_email,
            merchant_name=self.settings.MAIL_FROM_NAME,
            support_email=self.settings.MAIL_FROM,
            ship_to=PackingSlipAddress(
                name=address.name,
                street=address.street,
                city=address.city,
                province=address.province,
                postal_code=address.postal_code,
                country=address.country,
                phone=address.phone,
            ),
            line=PackingSlipLine(
                product_name=self._product_name(job, specification),
                quantity=job.quantity,
                unit_price=job.order_item.price if job.order_item else None,
                currency=order.currency.upper(),
            ),
            print_specification=self.describe_print(specification),
            notes=job.notes,
        )

    @staticmethod
    def parse_specification(job: CustomProductionJob) -> CustomTshirtSpecification | None:
        """Parse the production snapshot, tolerating a job without one.

        A job is queued from the signed customization captured at pricing
        time, so this normally parses. Returning ``None`` rather than raising
        keeps a malformed legacy row visible on the queue instead of breaking
        the whole listing.
        """
        if not job.specifications:
            return None
        try:
            return CustomTshirtSpecification(**job.specifications)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _product_name(
        job: CustomProductionJob, specification: CustomTshirtSpecification | None
    ) -> str:
        fulfillment = job.order_item.fulfillment if job.order_item else None
        if fulfillment and fulfillment.product_name:
            return fulfillment.product_name
        if specification:
            return f"Custom T-Shirt ({specification.size})"
        return "Custom T-Shirt"

    @staticmethod
    def describe_print(
        specification: CustomTshirtSpecification | None,
    ) -> PrintSpecification | None:
        if specification is None:
            return None
        return PrintSpecification(
            size=specification.size,
            garment_color=specification.garment_color,
            gender=specification.gender,
            placement=specification.placement,
            style=specification.style,
            prompt=specification.prompt,
            print_width_in=specification.print_width_in,
            print_height_in=specification.print_height_in,
            effective_dpi=specification.effective_dpi,
            artwork_key=specification.design_asset.key,
            artwork_sha256=specification.design_asset.sha256,
            artwork_width_px=specification.design_asset.width_px,
            artwork_height_px=specification.design_asset.height_px,
        )
