from datetime import timedelta, datetime, timezone
from typing import Annotated
from uuid import UUID
from webbrowser import get

from passlib.context import CryptContext
from fastapi import Depends, HTTPException, HTTPException
from pydantic import EmailStr
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from shared.schemas.user_schemas import CurrentUserInfo



# Password hashing context


# OAuth2PasswordBearer is a class that provides a way to extract the token from the request
# scheme_name is similar to variable name
#oauth2_scheme = OAuth2PasswordBearer(
#    tokenUrl=settings.TOKEN_URL,
#    scheme_name="oauth2_scheme",   
#)

# Global (lazy) oauth2 scheme holder to avoid class-body self reference NameError
oauth2_scheme: OAuth2PasswordBearer | None = None

def get_oauth2_scheme() -> OAuth2PasswordBearer:
    if oauth2_scheme is None:
        # Should not happen after AuthenticationManager initialization
        raise RuntimeError("OAuth2PasswordBearer not initialized yet")
    return oauth2_scheme

 


class AuthenticationManager:
    """
    This class handles password hashing, token creation, and user authentication.
    It uses the settings from the shared settings module for configuration.
    """
    
    def __init__(self, settings):
        self.settings = settings
        self.initialized = True
        self.token_expire_minutes = self.settings.TIME_DELTA_MINUTES
        self.pwd_context = CryptContext(schemes=settings.CRYPT_CONTEXT_SCHEME, deprecated="auto")
        
        # Initialize global oauth2 scheme once
        # TODO: i really dont like how its done...need to find a better way
        # TODO: and the problem is that it was initialized outisde of the class and works well, but i cant import setting coz of circular import
        global oauth2_scheme
        if oauth2_scheme is None:
            oauth2_scheme = OAuth2PasswordBearer(
                tokenUrl=settings.TOKEN_URL,
                scheme_name="oauth2_scheme"
            )
        
    def hash_password(self, entered_password: str) -> str:
        """Hash password using bcrypt with caching for frequently used passwords"""
        return self.pwd_context.hash(entered_password)
    
    def _verify_password(self, entered_password: str, hashed_password: str) -> bool:
        return self.pwd_context.verify(entered_password, hashed_password)

    def create_access_token(self, 
                            email: EmailStr, 
                            user_id: UUID, 
                            role: str | None, 
                            expires_delta: timedelta,
                            purpose: str = "access") -> tuple[str, int]:
        """Creating JWT access token"""
        expire_timestamp = int((datetime.now(timezone.utc) + expires_delta).timestamp())
        payload = {
            'sub': email,
            'id': str(user_id),
            'role': role,
            'exp': expire_timestamp,
            'purpose': purpose
        }
        token = jwt.encode(payload, self.settings.SECRET_KEY, algorithm=self.settings.ALGORITHM)
        return token, expire_timestamp

    def decode_token(self, token: str, required_purpose: str = "access") -> dict:
        """Decode JWT token and validate its purpose"""
        try:
            payload = jwt.decode(token, self.settings.SECRET_KEY, algorithms=[self.settings.ALGORITHM])
            purpose: str | None = payload.get('purpose', required_purpose) # Default to "access" if not specified

            email: str | None = payload.get('sub')
            user_id: str | None = payload.get("id")
            role: str | None = payload.get("role")
            purpose: str | None = payload.get('purpose', required_purpose) # Default to "access" if not specified   
            
            if not email or not user_id:
                raise HTTPException(status_code=401, detail="User's email or id is not provided / verified.")
               
            if purpose != required_purpose:
                raise HTTPException(status_code=401, detail=f"Invalid token purpose. Expected: {required_purpose}, got: {purpose}")

            return {
                "email": email,
                "id": user_id,
                "role": role,
                "purpose": purpose
            }
        
        except JWTError as jwt_error:
            raise HTTPException(status_code=401, detail=f"Token error: {str(jwt_error)}")
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Token decoding error: {str(e)}")

    async def authenticate_user(self,
                            email: EmailStr, 
                            password: str, 
                            user_service) -> CurrentUserInfo: 
        """Authenticate user with email and password"""
        users_hashed_password = await user_service.get_user_hashed_password(email=email)
            
        if not self._verify_password(password, users_hashed_password):
            raise HTTPException(status_code=401, detail="Incorrect email or password")
        
        
        #TODO : check if needed verification logic of user
        user = await user_service.get_user_by_email(email=email)
            
        if not user.is_verified:
            raise HTTPException(status_code=401, detail="User is not verified")
            
        return CurrentUserInfo(
            email=user.email,
            id=user.id,
            role=user.role
        )
    
    async def get_current_user_from_token(self, 
                                          token: Annotated[str, Depends(get_oauth2_scheme)],
                                          required_purpose: str = "access") -> CurrentUserInfo:
        """Checking if user is logged in and with valid token"""
        token_data = self.decode_token(token, required_purpose=required_purpose)
        return CurrentUserInfo(
            email=token_data["email"],
            id=token_data["id"],
            role=token_data["role"]
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
            


            
            


