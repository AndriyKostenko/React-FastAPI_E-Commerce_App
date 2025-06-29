from datetime import timedelta, datetime, timezone
from typing import Annotated
from uuid import UUID
from passlib.context import CryptContext

from fastapi import Depends
from pydantic import ValidationError, EmailStr
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm


from errors.errors import UserPasswordError, UserIsNotVerifiedError
from config import get_settings
from schemas.user_schemas import CurrentUserInfo



# Password hashing context
pwd_context = CryptContext(schemes=get_settings().CRYPT_CONTEXT_SCHEME, deprecated="auto")

# OAuth2PasswordBearer is a class that provides a way to extract the token from the request
# sceme_name is similar to variable name
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=get_settings().TOKEN_URL,
    scheme_name="oauth2_scheme",   
)

 

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
            self.token_expire_minutes = self.settings.TIME_DELTA_MINUTES
           
       
    def hash_password(self, entered_password: str) -> str:
        """Hash password using bcrypt with caching for frequently used passwords"""
        return pwd_context.hash(entered_password)
    
    @staticmethod
    def _verify_password(entered_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(entered_password, hashed_password)
    
    async def authenticate_user(self, 
                                email: EmailStr, 
                                password: str, 
                                user_service) -> CurrentUserInfo: 
        """Authenticate user with email and password"""
        users_hashed_password = await user_service.get_users_hashed_password(email=email)
            
        if not self._verify_password(password, users_hashed_password):
            raise UserPasswordError(detail='Invalid password')
        
        
        #TODO : check if needed verification logic of user
        user = await user_service.get_user_by_email(email=email)
            
        # if not user.is_verified:
        #     raise UserIsNotVerifiedError(detail='User is not verified')
            
        return CurrentUserInfo(
            email=user.email,
            id=user.id,
            role=user.role)
            
    def create_access_token(self, 
                            email: EmailStr, 
                            user_id: UUID, 
                            role: str, 
                            expires_delta: timedelta,
                            purpose: str = "access"):
        """Creating JWT access token"""
        expire_timestamp = int((datetime.now(timezone.utc) + expires_delta).timestamp())
        payload = {'sub': email,
                  'id': str(user_id),
                  'role': role,
                  'exp': expire_timestamp,
                  'purpose': purpose
                  }
        token = jwt.encode(payload, self.settings.SECRET_KEY, algorithm=self.settings.ALGORITHM)
        return token, expire_timestamp
    
    async def get_current_user_from_token(self, 
                                          token: Annotated[str, Depends(oauth2_scheme)],
                                          required_purpose: str = "access") -> CurrentUserInfo:
        """Checking if user is logged in and with valid token"""
        try:
            payload = jwt.decode(token, self.settings.SECRET_KEY, algorithms=[self.settings.ALGORITHM])
            email: str = payload.get('sub')
            user_id: str = payload.get('id')
            role: str = payload.get('role')
            exp: int = payload.get('exp')
            purpose: str = payload.get('purpose', required_purpose) # Default to "access" if not specified
            
            if not email or not user_id:
                raise UserIsNotVerifiedError(detail=f"User's email or id is not provided / verified.")
            
            # Only check purpose if it's specifically required (for special tokens)
            if purpose != required_purpose:
                raise UserIsNotVerifiedError(detail=f"Invalid token purpose. Expected: {required_purpose}, got: {purpose}")

            return CurrentUserInfo(email=email, 
                                   id=user_id, 
                                   role=role, 
                                   exp=exp)
            
        except JWTError as jwt_error:
            raise UserIsNotVerifiedError(
                detail=f"Invalid token: {str(jwt_error)}"
            )

    
    async def get_authenticated_user(self,
                                    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                                    user_crud_service):
        """Authenticate user with credentials"""
        return await self.authenticate_user(
            email=form_data.username,
            password=form_data.password,
            user_service=user_crud_service
        )
            
            
# Initialize the AuthenticationManager instance
auth_manager = AuthenticationManager()

            
            


