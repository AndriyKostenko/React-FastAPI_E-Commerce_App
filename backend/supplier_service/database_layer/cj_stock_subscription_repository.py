from collections.abc import Collection
from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.cj_stock_subscription_models import CJStockSubscription, CJStockSubscriptionVariant
from shared.contracts.supplier import SupplierStockKey
from shared.database_layer.database_layer import BaseRepository


class CJStockSubscriptionRepository(BaseRepository[CJStockSubscription]):
    """The CJ products we sell, their variants, and which CJ pushes stock for."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CJStockSubscription)

    async def pids_for_vids(self, vids: Collection[str]) -> dict[str, str]:
        """Variant id -> product id, for the variants of products we sell."""
        if not vids:
            return {}
        result = await self.session.execute(
            select(CJStockSubscriptionVariant.vid, CJStockSubscriptionVariant.pid).where(
                CJStockSubscriptionVariant.vid.in_(list(vids))
            )
        )
        return {vid: pid for vid, pid in result.all()}

    async def record_catalogue(self, keys: list[SupplierStockKey]) -> None:
        """
        Make the listed products and their variants current.

        A new product is added unsubscribed; a known one keeps its
        subscription. Its variants are replaced, so a variant product-service
        no longer sells stops being mapped. Products missing from ``keys`` are
        left for the caller to unsubscribe.
        """
        if not keys:
            return
        pids = list(dict.fromkeys(key.supplier_pid for key in keys))
        await self.session.execute(
            insert(CJStockSubscription)
            .values([{"pid": pid} for pid in pids])
            .on_conflict_do_nothing(index_elements=["pid"])
        )
        await self.session.execute(
            delete(CJStockSubscriptionVariant).where(CJStockSubscriptionVariant.pid.in_(pids))
        )
        # A vid is CJ's and belongs to one product; should two products we sell
        # ever list the same one, the later listing wins. Deduplicated here,
        # because one INSERT ... ON CONFLICT cannot touch the same row twice.
        owner = {vid: key.supplier_pid for key in keys for vid in key.vids}
        rows = [{"vid": vid, "pid": pid} for vid, pid in owner.items()]
        if rows:
            statement = insert(CJStockSubscriptionVariant).values(rows)
            await self.session.execute(
                statement.on_conflict_do_update(
                    index_elements=["vid"], set_={"pid": statement.excluded.pid}
                )
            )
        await self.session.flush()

    async def list_unsubscribed_pids(self) -> list[str]:
        result = await self.session.execute(
            select(CJStockSubscription.pid)
            .where(CJStockSubscription.subscribed_at.is_(None))
            .order_by(CJStockSubscription.pid)
        )
        return list(result.scalars().all())

    async def list_not_in(self, pids: Collection[str]) -> list[CJStockSubscription]:
        """Recorded products that are not among ``pids``: no longer sold."""
        statement = select(CJStockSubscription).order_by(CJStockSubscription.pid)
        if pids:
            statement = statement.where(CJStockSubscription.pid.not_in(list(pids)))
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def mark_subscribed(self, pids: Collection[str], at: datetime) -> None:
        if not pids:
            return
        await self.session.execute(
            update(CJStockSubscription)
            .where(CJStockSubscription.pid.in_(list(pids)))
            .values(subscribed_at=at)
        )

    async def remove(self, pids: Collection[str]) -> None:
        """Forget products (their variants go with them)."""
        if not pids:
            return
        await self.session.execute(
            delete(CJStockSubscription).where(CJStockSubscription.pid.in_(list(pids)))
        )
        await self.session.flush()
