from logging import Logger
from uuid import UUID

from service_layer.design_retention import DesignRefusalRetention, DesignRetention


class DeletedAccountCleanup:
    """
    What product-service lets go of when an account is deleted: its unordered
    designs, and its id on refusal records (which stay, anonymous, for the
    admins). Ordered designs stay with their orders; reviews hold only the id
    and show no name.
    """

    def __init__(self, designs: DesignRetention, refusals: DesignRefusalRetention, logger: Logger) -> None:
        self._designs = designs
        self._refusals = refusals
        self._logger = logger

    async def forget(self, user_id: UUID) -> None:
        designs = await self._designs.forget_user(user_id)
        refusals = await self._refusals.forget_user(user_id)
        self._logger.info(
            "Deleted account %s: %s unordered designs deleted, %s refusals anonymised", user_id, designs, refusals
        )
