from sqlalchemy.ext.asyncio import AsyncSession
import bcrypt
from sqlalchemy import select, asc

from src.models.user_models import User
from src.schemas.user_schemas import UserSignUp, DeleteUser, UserUpdate
from src.errors.user_service_errors import user_service_error_factory
from src.errors.database_errors import DatabaseError
from sqlalchemy.exc import SQLAlchemyError



# the service needs a database session which is request-scoped
# each request should have its own isolated session for transaction safety
# FastAPI dependency injection system is designed to work this way
class UserCRUDService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _hash_password(self, entered_password: str) -> str:
        return bcrypt.hashpw(entered_password.encode(), bcrypt.gensalt()).decode()

    def _verify_password(self, entered_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(entered_password.encode(), hashed_password.encode())

    async def create_user(self, user: UserSignUp):
        try:
            db_user = await self.get_user_by_email(user.email)
            if db_user:
                raise UserCreationError(detail=f"User with email: {user.email} already exists")
            hashed_password = self._hash_password(user.password)
            new_user = User(name=user.name,
                            email=user.email,
                            hashed_password=hashed_password)
            # not using await coz it's an in-memory operation and doesn't interact with db
            self.session.add(new_user)

            # the commit and refresh methods are an asynchronous operations because they involve writing the
            # changes to the database, which is an I/O operation
            await self.session.commit()
            await self.session.refresh(new_user)
            return new_user
        except SQLAlchemyError as error:
            raise DatabaseError(detail=str(error))

    async def get_all_users(self):
        result = await self.session.execute(select(User).order_by(asc(User.id)))
        return result.scalars().all()

    async def get_user_by_email(self, email: str):
        db_user = await self.session.execute(select(User).where(User.email == email))
        user = db_user.scalars().first()
        return user

    async def get_user_by_id(self, user_id: int):
        db_user = await self.session.execute(select(User).where(User.id == user_id))
        user = db_user.scalars().first()
        return user  # Returns None if user is not found

    async def update_user_by_id(self, user_id: int, user_update_data: UserUpdate):
        db_user = await self.get_user_by_id(user_id)
        if not db_user:
            return None
        db_user.name = user_update_data.name
        db_user.hashed_password = self._hash_password(user_update_data.password)
        await self.session.commit()
        return db_user

    async def delete_user_by_id(self, user_id: int):
        user_to_delete = await self.get_user_by_id(user_id)
        await self.session.delete(user_to_delete)
        await self.session.commit()

    #TODO: Transfer this method to the authentication service
    # taking email for authentication coz its unique (but in OAth2 form it will be written as 'username')
    async def authenticate_user(self, email: str, entered_password: str):
        db_user = await self.get_user_by_email(email)
        if not db_user:
            return False
        if not self._verify_password(entered_password=entered_password, hashed_password=db_user.hashed_password):
            return False
        return db_user



