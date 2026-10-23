from uuid import UUID

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
