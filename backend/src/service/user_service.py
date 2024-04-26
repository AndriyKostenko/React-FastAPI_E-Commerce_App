from sqlalchemy.ext.asyncio import AsyncSession
from src.models.user_model import User
import bcrypt
from sqlalchemy import select, asc, desc
from src.schemas.user_schemas import UserSignUp, DeleteUser, UserUpdate


class UserCRUDService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _hash_password(self, entered_password: str) -> str:
        return bcrypt.hashpw(entered_password.encode(), bcrypt.gensalt()).decode()

    def _verify_password(self, entered_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(entered_password.encode(), hashed_password.encode())

    async def create_user(self, user: UserSignUp):
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

    async def get_all_users(self):
        result = await self.session.execute(select(User).order_by(asc(User.id)))
        users = result.scalars().all()
        return users

    async def get_user_by_email(self, email: str):
        db_user = await self.session.execute(select(User).where(User.email == email))
        return db_user.scalars().first()

    async def get_user_by_id(self, user_id: int):
        db_user = await self.session.execute(select(User).where(User.id == user_id))
        return db_user.scalars().first()

    async def update_user_by_id(self, user_id: int, user_update_data: UserUpdate):
        db_user = await self.get_user_by_id(user_id)
        db_user.name = user_update_data.name
        db_user.hashed_password = self._hash_password(user_update_data.password)
        await self.session.commit()
        return db_user

    async def delete_user_by_id(self, user_id: int):
        user_to_delete = await self.get_user_by_id(user_id)
        await self.session.delete(user_to_delete)
        await self.session.commit()

    # taking email for authentication coz its unique (but in OAth2 form it will be written as 'username')
    async def authenticate_user(self, email: str, entered_password: str):
        db_user = await self.get_user_by_email(email)
        if not db_user:
            return False
        if not self._verify_password(entered_password=entered_password, hashed_password=db_user.hashed_password):
            return False
        return db_user
