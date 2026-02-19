# shared/token_manager.py
from datetime import timedelta, datetime, timezone
from uuid import UUID

from jose import jwt, JWTError
from fastapi import HTTPException
from pydantic import EmailStr

from shared.settings import Settings
from shared.schemas.user_schemas import DecodedTokenSchema


class TokenManager:
    """
    Handles JWT token creation and validation.
    """

    def __init__(self, settings: Settings):
        self.settings: Settings = settings

    def create_access_token(self,
                            email: EmailStr,
                            user_id: UUID,
                            role: str | None,
                            expires_delta: timedelta,
                            purpose: str = "access") -> tuple[str, int]:
        """
        Create JWT access token.

        Returns:
            tuple: (token, expire_timestamp)
        """
        expire_timestamp = int((datetime.now(timezone.utc) + expires_delta).timestamp())
        payload = {
            'sub': email,
            'id': str(user_id),
            'role': role,
            'exp': expire_timestamp,
            'purpose': purpose
        }
        token = jwt.encode(
            payload,
            self.settings.SECRET_KEY,
            algorithm=self.settings.ALGORITHM
        )
        return token, expire_timestamp

    def decode_token(self, token: str, required_purpose: str = "access") -> DecodedTokenSchema:
        """
        Decode JWT token and validate its purpose.

        Raises:
            HTTPException: If token is invalid or purpose doesn't match
        """
        try:
            payload = jwt.decode(
                token,
                self.settings.SECRET_KEY,
                algorithms=[self.settings.ALGORITHM]
            )

            email: EmailStr | None = payload.get("sub")
            user_id: UUID | None = payload.get("id")
            role: str | None = payload.get("role")
            purpose: str | None = payload.get("purpose", required_purpose)

            if not email or not user_id:
                raise HTTPException(
                    status_code=401,
                    detail="User's email or id is not provided/verified for token decoding."
                )

            if purpose != required_purpose:
                raise HTTPException(
                    status_code=401,
                    detail=f"Invalid token purpose. Expected: {required_purpose}, got: {purpose}"
                )

            return DecodedTokenSchema(
                email=email,
                id=user_id,
                role=role,
                purpose=purpose
            )


        except JWTError as jwt_error:
            raise HTTPException(
                status_code=401,
                detail=f"Token error: {str(jwt_error)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=401,
                detail=f"Token decoding error: {str(e)}"
            )

    def validate_token(self, token: str, required_purpose: str = "access") -> bool:
        """
        Validate a token without decoding all data.

        Returns:
            bool: True if valid, False otherwise
        """
        try:
            self.decode_token(token, required_purpose)
            return True
        except HTTPException:
            return False
