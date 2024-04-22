from sqlalchemy.orm import Session

from app.models.user_models import User
from app.schemas.users_schema import UserSignUp
from app.security.security import get_hashed_password


async def create_user(db: Session, user: UserSignUp):
    db_user = User(name=user.name,
                   email=user.email,
                   hashed_password=get_hashed_password(user.password))
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


async def delete_user_(db: Session, user_email: str):
    user_ = db.query(User).filter(User.email == user_email).first()
    db.delete(user_)
    db.commit()
    return db.query(User).all()


async def get_user_by_email(db: Session, user_email: str):
    user = db.query(User).filter(User.email == user_email).first()
    return user


async def get_users(db: Session):
    return db.query(User).all()