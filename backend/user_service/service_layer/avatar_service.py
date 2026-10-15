from uuid import UUID

from fastapi import HTTPException, status

from database_layer.user_repository import UserRepository
from exceptions.user_exceptions import UserNotFoundError
from managers import logger
from models.user_models import User
from schemas.user_schemas import UserInfo
from storage.avatar_storage import (
    AvatarImageProcessor,
    AvatarKeys,
    AvatarStorageUnavailableError,
    AvatarStore,
    InvalidAvatarError,
)


class AvatarService:
    """
    A user's own avatar: upload, remove, and clean-up when the account goes.

    Order of a replacement: the new object is written first, then the row
    points at it, then the old object is deleted -- so the row never names a
    missing file. Only keys this service stored for the user are ever deleted;
    a Google profile picture URL is just forgotten.
    """

    def __init__(self, users: UserRepository, store: AvatarStore | None, processor: AvatarImageProcessor) -> None:
        self._users = users
        self._store = store
        self._processor = processor

    def _require_store(self) -> AvatarStore:
        if self._store is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Avatar uploads are not available right now",
            )
        return self._store

    async def _user(self, user_id: UUID) -> User:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(f"User with id: {user_id} not found.")
        return user

    async def upload(self, user_id: UUID, content: bytes) -> UserInfo:
        store = self._require_store()
        try:
            avatar = self._processor.process(content)
        except InvalidAvatarError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error

        user = await self._user(user_id)
        previous = user.image
        key = AvatarKeys.new(user_id)
        await self._put(store, key, avatar)
        updated = await self._users.update_by_id(item_id=user_id, data={"image": key})
        if AvatarKeys.owned_by(previous, user_id):
            await self._delete_quietly(store, str(previous))
        return UserInfo.model_validate(updated)

    async def remove(self, user_id: UUID) -> UserInfo:
        user = await self._user(user_id)
        previous = user.image
        updated = await self._users.update_by_id(item_id=user_id, data={"image": None})
        if AvatarKeys.owned_by(previous, user_id) and self._store is not None:
            await self._delete_quietly(self._store, str(previous))
        return UserInfo.model_validate(updated)

    async def forget(self, user_id: UUID) -> None:
        """
        Delete the stored avatar as part of deleting the account.

        Strict, unlike a replacement: the file is public personal data, so if
        it cannot be deleted the account deletion fails and can be retried,
        rather than leaving the picture online with no account to remove it from.
        """
        user = await self._users.get_by_id(user_id)
        if user is None or not AvatarKeys.owned_by(user.image, user_id):
            return
        store = self._require_store()
        try:
            await store.delete(str(user.image))
        except AvatarStorageUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Your account could not be deleted right now; please try again",
            ) from error

    @staticmethod
    async def _put(store: AvatarStore, key: str, content: bytes) -> None:
        try:
            await store.put(key, content)
        except AvatarStorageUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Your picture could not be saved right now; please try again",
            ) from error

    @staticmethod
    async def _delete_quietly(store: AvatarStore, key: str) -> None:
        # The old picture is no longer referenced; failing to delete it must not
        # fail the change the user asked for. It is left behind, unlisted.
        try:
            await store.delete(key)
        except AvatarStorageUnavailableError:
            logger.warning("Could not delete a replaced avatar", extra={"key": key})
