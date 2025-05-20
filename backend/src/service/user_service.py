from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, asc


from src.security.authentication import auth_manager
from src.models.user_models import User
from src.schemas.user_schemas import UserSignUp, UserUpdate, UserInfo
from src.errors.user_service_errors import (UserNotFoundError, 
                                            UserAlreadyExistsError)




# the service needs a database session which is request-scoped
# each request should have its own isolated session for transaction safety
# FastAPI dependency injection system is designed to work this way
class UserCRUDService:
    def __init__(self, session: AsyncSession):
        self.session = session


    async def create_user(self, user: UserSignUp) -> UserInfo:
        db_user = await self.get_user_by_email(user.email)
        
        if db_user:
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
        return UserInfo(id=new_user.id,
                        name=new_user.name,
                        email=new_user.email,
                        role=new_user.role,
                        phone_number=new_user.phone_number,
                        date_created=new_user.date_created,
                        image=new_user.image,
                        date_updated=new_user.date_updated)
       

    async def get_all_users(self):
        result = await self.session.execute(select(User).order_by(asc(User.id)))
        return result.scalars().all()
    
    # @handle_db_errors
    async def get_user_by_email(self, email: str):
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalars().first() # will be returned as None if not found
        
  
    async def get_user_by_id(self, user_id: str):
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalars().first() # will be returned as None if not found


    async def update_user_by_id(self, user_id: str, user_update_data: UserUpdate):
        db_user = await self.get_user_by_id(user_id)
        if not db_user:
            raise UserNotFoundError(detail=f'User with id: "{user_id}" not found')
        db_user.name = user_update_data.name
        db_user.hashed_password = auth_manager.hash_password(user_update_data.password)
        await self.session.commit()
        await self.session.refresh(db_user)
        return db_user
    

    async def update_user_verified_status(self, user_email: str, verified: bool):
        db_user = await self.get_user_by_email(user_email)
        if not db_user:
            raise UserNotFoundError(detail=f'User with email: "{user_email}" not found')
        db_user.is_verified = verified
        await self.session.commit()
        await self.session.refresh(db_user)
        return db_user
    
    async def update_user_password(self, user_email: str, new_password: str):
        db_user = await self.get_user_by_email(user_email)
        if not db_user:
            raise UserNotFoundError(detail=f'User with email: {user_email} is not found')
        db_user.hashed_password = auth_manager.hash_password(new_password)
        await self.session.commit()
        await self.session.refresh(db_user)
        return db_user
    

    async def delete_user_by_id(self, user_id: str):
        user_to_delete = await self.get_user_by_id(user_id)
        await self.session.delete(user_to_delete)
        await self.session.commit()




