import pytest
from jose import jwt
from src.config import settings
from src.security.authentication import get_current_user
from fastapi import HTTPException
# marking with package to use same event_loop() for all tests in package
pytestmark = pytest.mark.asyncio(scope="package")


async def test_get_current_user():
    encode = {'sub': 'test_user',
              'id': 1,
              'role': 'admin'}
    token = jwt.encode(encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    user = await get_current_user(token)

    assert user == {'email': 'test_user', 'id': 1, 'user_role': 'admin'}


async def test_get_current_user_invalid_token():
    encode = {'role': 'user'}
    token = jwt.encode(encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    with pytest.raises(HTTPException) as exceptionInfo:
        await get_current_user(token=token)

    assert exceptionInfo.value.status_code == 401
    assert exceptionInfo.value.detail == 'Could not validate user'
