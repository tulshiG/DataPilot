from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.auth import UserRegister
from app.core.security import hash_password, verify_password
from app.core.exceptions import BadRequestException

def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()

def create_user(db: Session, user_data: UserRegister) -> User:
    existing_user = get_user_by_email(db, user_data.email)
    if existing_user:
        raise BadRequestException("Email already registered")

    new_user = User(
        full_name=user_data.full_name,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

def authenticate_user(db: Session, email: str, password: str) -> User | None:
    print(f"\n[DEBUG LOGIN] Attempting login for email: {email}")
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user