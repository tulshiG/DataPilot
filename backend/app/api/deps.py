from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.security import decode_access_token
from app.core.exceptions import CredentialsException
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_access_token(token)
    if payload is None:
        raise CredentialsException()

    user_id = payload.get("sub")
    if user_id is None:
        raise CredentialsException()

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise CredentialsException()

    return user