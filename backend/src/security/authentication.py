from datetime import timedelta, datetime
from typing import Annotated
from fastapi import Depends
from pydantic import ValidationError
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import bcrypt
from functools import lru_cache
from src.errors.user_service_errors import (UserNotFoundError,
                                            UserPasswordError,
                                            )

from src.config import get_settings
from src.schemas.user_schemas import CurrentUserInfo
from src.errors.user_service_errors import UserIsNotVerifiedError



# OAuth2PasswordBearer is a class that provides a way to extract the token from the request
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=get_settings().TOKEN_URL,
    scheme_name="oauth2_scheme",   
) # sceme_name is similar to variable name

# using a Singleton pattern to create only one instance of AuthenticationManager
# this is to avoid creating multiple instances of the same class
class AuthenticationManager:
    _instance = None
    

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AuthenticationManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.settings = get_settings()
            self.initialized = True
            self.token_expire_minutes = get_settings().TIME_DELTA_MINUTES
       
    
    @lru_cache(maxsize=None)     
    def hash_password(self, entered_password: str) -> str:
        """Hash password using bcrypt with caching for frequently used passwords"""
        return bcrypt.hashpw(entered_password.encode(), bcrypt.gensalt()).decode()
    
    @staticmethod
    def _verify_password(entered_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(entered_password.encode(), hashed_password.encode())
    
    
  
    async def authenticate_user(self, 
                                email: str, 
                                password: str, 
                                user_service) -> CurrentUserInfo: # type: ignore
        """Authenticate user with email and password"""
        user = await user_service._get_user_by_email_internal(email)
        if not user:
            raise UserNotFoundError(detail=f'User with email: "{email}" not found')
            
        if not self._verify_password(password, user.hashed_password):
            raise UserPasswordError(detail='Invalid password')
            
        if not user.is_verified:
            raise UserIsNotVerifiedError(detail='User is not verified')
            
        return CurrentUserInfo(
            email=user.email,
            id=user.id,
            user_role=user.role,
            exp=None) ## exp will be set when creating token
            
    def create_access_token(self, 
                            email: str, 
                            user_id: str, 
                            role: str, 
                            expires_delta: timedelta,
                            purpose: str = "access") -> str:
        """Creating JWT access token"""
        expire = int((datetime.utcnow() + expires_delta).timestamp())
        
        encode = {'sub': email,
                  'id': str(user_id),
                  'role': role,
                  'exp': expire,
                  'purpose': purpose
                  }
        return jwt.encode(encode, self.settings.SECRET_KEY, algorithm=self.settings.ALGORITHM)
    
    async def get_current_user_from_token(self, 
                                          token: Annotated[str, Depends(oauth2_scheme)],
                                          required_purpose: str = "access") -> CurrentUserInfo:
        """Checking if user is logged in and with valid token"""
        try:
            payload = jwt.decode(token, self.settings.SECRET_KEY, algorithms=[self.settings.ALGORITHM])
            email: str = payload.get('sub')
            user_id: str = payload.get('id')
            user_role: str = payload.get('role')
            exp: int = payload.get('exp')
            purpose: str = payload.get('purpose', required_purpose) # Default to "access" if not specified
            
            if not email or not user_id:
                raise UserIsNotVerifiedError(detail=f"User's email or id is not provided / verified.")
            
            # Only check purpose if it's specifically required (for special tokens)
            if purpose != required_purpose:
                raise UserIsNotVerifiedError(detail=f"Invalid token purpose. Expected: {required_purpose}, got: {purpose}")

            return CurrentUserInfo(email=email, 
                                   id=user_id, 
                                   user_role=user_role, 
                                   exp=exp)
            
        except JWTError as jwt_error:
            raise UserIsNotVerifiedError(
                detail=f"Invalid token: {str(jwt_error)}"
            )
        except ValidationError as val_error:
            raise UserIsNotVerifiedError(
                detail=f"Invalid token data: {str(val_error)}"
            )
    
    async def get_authenticated_user(self,
                                    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                                    user_service):
        """Authenticate user with credentials"""
        return await self.authenticate_user(
            email=form_data.username,
            password=form_data.password,
            user_service=user_service
        )
            
            
# Initialize the AuthenticationManager instance
auth_manager = AuthenticationManager()

            
            


