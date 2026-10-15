from uuid import UUID

from fastapi import HTTPException, status

from database_layer.address_repository import AddressRepository
from models.address_models import UserAddress
from schemas.address_schemas import AddressInput, AddressRead


class AddressService:
    """
    A customer's address book.

    Rules for the default address, the one checkout fills in:
    - a user with any addresses has exactly one default; the first address
      saved becomes it;
    - the default moves only when another address is made the default, so
      saving the default with ``is_default=False`` leaves it the default;
    - deleting the default promotes the oldest remaining address.

    Every change that can move the default locks the user's address book first
    (see ``AddressRepository.lock_address_book``).
    """

    MAX_ADDRESSES_PER_USER = 10

    def __init__(self, repository: AddressRepository) -> None:
        self._addresses = repository

    async def list_addresses(self, user_id: UUID) -> list[AddressRead]:
        return [AddressRead.model_validate(row) for row in await self._addresses.list_for_user(user_id)]

    async def create_address(self, user_id: UUID, data: AddressInput) -> AddressRead:
        await self._addresses.lock_address_book(user_id)
        count = await self._addresses.count_for_user(user_id)
        if count >= self.MAX_ADDRESSES_PER_USER:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"You can save up to {self.MAX_ADDRESSES_PER_USER} addresses; delete one first",
            )

        # The first address is the default whatever was asked.
        make_default = data.is_default or count == 0
        if make_default and count > 0:
            await self._addresses.clear_default(user_id)

        row = UserAddress(user_id=user_id, **data.model_dump(exclude={"is_default"}), is_default=make_default)
        return AddressRead.model_validate(await self._addresses.create(row))

    async def replace_address(self, user_id: UUID, address_id: UUID, data: AddressInput) -> AddressRead:
        await self._addresses.lock_address_book(user_id)
        row = await self._owned(user_id, address_id)

        if data.is_default and not row.is_default:
            await self._addresses.clear_default(user_id)
            row.is_default = True

        for field, value in data.model_dump(exclude={"is_default"}).items():
            setattr(row, field, value)
        await self._addresses.session.flush()
        await self._addresses.session.refresh(row)
        return AddressRead.model_validate(row)

    async def make_default(self, user_id: UUID, address_id: UUID) -> AddressRead:
        await self._addresses.lock_address_book(user_id)
        row = await self._owned(user_id, address_id)
        if not row.is_default:
            await self._addresses.clear_default(user_id)
            row.is_default = True
            await self._addresses.session.flush()
            await self._addresses.session.refresh(row)
        return AddressRead.model_validate(row)

    async def delete_address(self, user_id: UUID, address_id: UUID) -> None:
        await self._addresses.lock_address_book(user_id)
        row = await self._owned(user_id, address_id)
        was_default = row.is_default
        await self._addresses.delete(row)

        if was_default:
            successor = await self._addresses.oldest_for_user(user_id)
            if successor is not None:
                successor.is_default = True
                await self._addresses.session.flush()

    async def delete_all(self, user_id: UUID) -> None:
        """Every address the user saved: part of deleting their account."""
        await self._addresses.delete_all_for_user(user_id)

    async def _owned(self, user_id: UUID, address_id: UUID) -> UserAddress:
        row = await self._addresses.get_for_user(user_id, address_id)
        if row is None:
            # Another user's address reads as missing: its existence is not revealed.
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")
        return row
