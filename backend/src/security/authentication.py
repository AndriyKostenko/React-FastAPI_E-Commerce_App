from datetime import timedelta, datetime
from typing import Annotated
from fastapi import HTTPException, Depends, status, APIRouter
from pydantic import ValidationError
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.db_setup import get_db_session
from src.service.user_service import UserCRUDService

# using a singleton pattern to create only one instance of AuthenticationManager
# this is to avoid creating multiple instances of the same class
class AuthenticationManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AuthenticationManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        # initialiaing only if not already done
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self.secret_key = settings.SECRET_KEY
            self.algorithm = settings.ALGORITHM
            self.token_expire_minutes = settings.TIME_DELTA_MINUTES
            self.oauth2_scheme = OAuth2PasswordBearer(tokenUrl=settings.TOKEN_URL)
            
    def create_access_token(self, 
                            email: str, 
                            user_id: str, 
                            role: str, 
                            expires_delta: timedelta):
        """Creating JWT access token"""
        encode = {'sub': email,
                  'id': user_id,
                  'role': role,
                  'exp': datetime.utcnow() + expires_delta
                  }
        return jwt.encode(encode, self.secret_key, algorithm=self.algorithm)
    
    async def get_current_user(self, 
                               token: Annotated[str, Depends(OAuth2PasswordBearer(tokenUrl=settings.TOKEN_URL))]):
        """Checking if user is logged in and with valid token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            email: str = payload.get('sub')
            user_id: int = payload.get('id')
            user_role: str = payload.get('role')
            exp: int = payload.get('exp')
            
            if not email or not user_id:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                    detail='Could not validate user')
            return {'email': email, 
                    'id': user_id, 
                    'user_role': user_role, 
                    'exp': exp}
        except (JWTError, ValidationError):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail='Could not validate user')
            
            
    async def get_authenticated_user(self,
                                     form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                                     session: AsyncSession = Depends(get_db_session)):
        """Authenticate user with credentials"""
        user = await UserCRUDService(session=session).authenticate_user(email=form_data.username,
                                                                entered_password=form_data.password)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail='Could not validate user')
        return user
            
            
auth_manager = AuthenticationManager()
            

