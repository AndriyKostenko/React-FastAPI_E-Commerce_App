from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.design_moderation_refusal_models import DesignModerationRefusal
from service_layer.design_moderation import DesignRefusal
from infrastructure.database_layer.database_layer import BaseRepository


class DesignModerationRefusalRepository(BaseRepository[DesignModerationRefusal]):
    """The designs the moderation check refused (the admins read them through AdminTable)."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, DesignModerationRefusal)

    async def record(
        self, user_id: UUID | None, prompt: str, style: str, refusal: DesignRefusal
    ) -> DesignModerationRefusal:
        return await self.create(
            DesignModerationRefusal(
                user_id=user_id,
                stage=refusal.stage.value,
                category=refusal.category.value,
                prompt=prompt,
                style=style,
                reason=refusal.reason,
                model=refusal.model,
            )
        )

    async def forget_user(self, user_id: UUID) -> int:
        """A deleted account's refusals stay for the admins, without the account's id."""
        result = await self.session.execute(
            update(DesignModerationRefusal).where(DesignModerationRefusal.user_id == user_id).values(user_id=None)
        )
        return result.rowcount or 0

    async def delete_created_before(self, cutoff: datetime, limit: int) -> int:
        """Delete up to ``limit`` refusals recorded before ``cutoff``, oldest first."""
        oldest = (
            select(DesignModerationRefusal.id)
            .where(DesignModerationRefusal.date_created < cutoff)
            .order_by(DesignModerationRefusal.date_created)
            .limit(limit)
        )
        result = await self.session.execute(
            delete(DesignModerationRefusal).where(DesignModerationRefusal.id.in_(oldest))
        )
        return result.rowcount or 0
