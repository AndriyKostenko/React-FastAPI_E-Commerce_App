from uuid import UUID
from fastapi import HTTPException, status, Depends, Request
from pydantic import EmailStr
from shared.shared_instances import settings, logger
from shared.schemas.user_schemas import CurrentUserInfo


def get_current_user(request: Request) -> CurrentUserInfo:
    """Get currrent user from the request state (set by auth middleware in main.py)"""
    current_user = getattr(request.state, "current_user", None)
    logger.info(f"Current user from request state: {current_user}")
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate" : "Bearer"}
        )
    return CurrentUserInfo(**current_user)


def require_admin(current_user: CurrentUserInfo = Depends(get_current_user)) -> CurrentUserInfo:
    """Require admin role for accessing endpoints"""
    if current_user.role != settings.SECRET_ROLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


def require_user_or_admin(current_user: CurrentUserInfo,
                          target_user_id: UUID | None = None,
                          target_user_email: EmailStr | None = None) -> CurrentUserInfo:
    is_admin = current_user.role == settings.SECRET_ROLE
    is_own_data = (
        (target_user_id and current_user.id == target_user_id) or
        (target_user_email and current_user.email == target_user_email)
    )

    if not (is_admin or is_own_data):
        logger.warning(f"User id: {target_user_id} and / or user email: {target_user_email} is trying to acces not personal data")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You can only access your own data"
        )
    return current_user
