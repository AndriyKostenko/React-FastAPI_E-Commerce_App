
from jose import jwt
from datetime import timedelta

from src.config import settings
from src.security.authentication import create_access_token


def test_create_access_token():
    username = 'test_user'
    user_id = 1
    role = 'admin'
    expires_delta = timedelta(minutes=15)

    token = create_access_token(username, user_id, role, expires_delta)

    decoded_token = jwt.decode(token,
                               settings.SECRET_KEY,
                               algorithms=[settings.ALGORITHM],
                               options={"verify_signature": False})

    assert decoded_token.get('sub') == username
    assert decoded_token.get('id') == user_id
    assert decoded_token.get('role') == role
