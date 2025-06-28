from hmac import new
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, asc
from pydantic import EmailStr

from authentication import auth_manager
from schemas import UserSignUp, UserBasicUpdate
from errors import (UserNotFoundError, 
                    UserAlreadyExistsError)

from models.user_models import User
from schemas.user_schemas import UserInfo, AllUsersInfo



# the service needs a database session which is request-scoped
# each request should have its own isolated session for transaction safety
# FastAPI dependency injection system is designed to work this way
class UserCRUDService:
    """Service class for user-related CRUD operations"""
    def __init__(self, session: AsyncSession):
        self.session = session
        

    async def _check_user_exists(self, email: str) -> bool:
        """Internal method to check if user exists without raising exceptions"""
        query = await self.session.execute(select(User).where(User.email == email))
        user = query.scalars().first()
        return user is not None
    
    async def create_user(self, user: UserSignUp) -> UserInfo:
        if await self._check_user_exists(user.email):
            raise UserAlreadyExistsError(detail=f'User with email: {user.email} already exists')
        hashed_password = auth_manager.hash_password(user.password)
        new_user = User(name=user.name,
                        email=user.email,
                        hashed_password=hashed_password,
                        is_verified=user.is_verified,
                        role=user.role,)
        # not using await coz it's an in-memory operation and doesn't interact with db
        self.session.add(new_user)
        # the commit and refresh methods are an asynchronous operations because they involve writing the
        # changes to the database, which is an I/O operation
        await self.session.commit()
        await self.session.refresh(new_user)
        return UserInfo.model_validate(new_user)
       

    async def get_all_users(self) -> AllUsersInfo:
        query = await self.session.execute(select(User).order_by(asc(User.id)))
        users = query.scalars().all() 
        return AllUsersInfo(users=[AllUsersInfo.model_validate(user) for user in users])
    
    
    async def get_user_by_email(self, email: EmailStr) -> UserInfo:
        query = await self.session.execute(select(User).where(User.email == email))
        user = query.scalars().first()
        if not user:
            raise UserNotFoundError(detail=f'User with email: "{email}" not found')
        return UserInfo.model_validate(user)
        
  
    async def get_user_by_id(self, user_id: UUID) -> UserInfo:
        result = await self.session.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()
        if not user:
            raise UserNotFoundError(detail=f'User with id: "{user_id}" not found')
        return UserInfo.model_validate(user)


    async def update_user_basic_info(self, user_id: UUID, user_update_data: UserBasicUpdate) -> UserInfo:
        """Update basic user information like name, phone, image"""
        db_user = await self.get_user_by_id(user_id)
        # Update only provided fields
        for field, value in user_update_data.model_dump().items():
            setattr(db_user, field, value)
        await self.session.commit()
        await self.session.refresh(db_user)
        return UserInfo.model_validate(db_user)
    

    async def update_user_verified_status(self, user_email: EmailStr, status: bool) -> UserInfo:
        db_user = await self.get_user_by_email(user_email)
        db_user.is_verified = status
        await self.session.commit()
        await self.session.refresh(db_user)
        return UserInfo.model_validate(db_user)
    
    
    async def update_user_password(self, email: EmailStr, new_password: str) -> UserInfo:
        db_user = await self.get_user_by_email(email=email)
        db_user.hashed_password = auth_manager.hash_password(new_password)
        await self.session.commit()
        await self.session.refresh(db_user)
        return UserInfo.model_validate(db_user)
    

    async def delete_user_by_id(self, user_id: UUID) -> None:
        user_to_delete = await self.get_user_by_id(user_id)
        await self.session.delete(user_to_delete)
        await self.session.commit()




