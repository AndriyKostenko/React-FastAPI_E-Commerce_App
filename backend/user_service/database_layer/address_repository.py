from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.address_models import UserAddress
from models.user_models import User
from infrastructure.database_layer.database_layer import BaseRepository


class AddressRepository(BaseRepository[UserAddress]):
    """Each customer's saved shipping addresses. Every query is scoped to one user."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, UserAddress)

    async def list_for_user(self, user_id: UUID) -> list[UserAddress]:
        """The default first, then oldest first: the order the address book shows."""
        result = await self.session.execute(
            select(UserAddress)
            .where(UserAddress.user_id == user_id)
            .order_by(UserAddress.is_default.desc(), UserAddress.date_created, UserAddress.id)
        )
        return list(result.scalars().all())

    async def count_for_user(self, user_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(UserAddress).where(UserAddress.user_id == user_id)
        )
        return int(result.scalar_one())

    async def get_for_user(self, user_id: UUID, address_id: UUID) -> UserAddress | None:
        """The address, only if it belongs to this user; another user's reads as missing."""
        result = await self.session.execute(
            select(UserAddress).where(UserAddress.id == address_id, UserAddress.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def lock_address_book(self, user_id: UUID) -> None:
        """
        Serialise changes to one user's address book until the transaction ends.

        Changing which address is the default touches two rows (the old default
        and the new one), and the first address becomes the default by itself.
        Locking the user's own row, which always exists even before the first
        address, makes concurrent changes for the same user run one after the
        other instead of tripping the one-default index or the address limit.
        """
        await self.session.execute(select(User.id).where(User.id == user_id).with_for_update())

    async def clear_default(self, user_id: UUID) -> None:
        await self.session.execute(
            update(UserAddress)
            .where(UserAddress.user_id == user_id, UserAddress.is_default.is_(True))
            .values(is_default=False)
        )
        await self.session.flush()

    async def oldest_for_user(self, user_id: UUID) -> UserAddress | None:
        result = await self.session.execute(
            select(UserAddress)
            .where(UserAddress.user_id == user_id)
            .order_by(UserAddress.date_created, UserAddress.id)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def delete_all_for_user(self, user_id: UUID) -> None:
        await self.session.execute(delete(UserAddress).where(UserAddress.user_id == user_id))
        await self.session.flush()
