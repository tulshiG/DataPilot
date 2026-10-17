from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.auth import UserRegister, UserLogin, UserOut, Token
from app.services import auth_service
from app.core.security import create_access_token
from app.core.exceptions import CredentialsException
from app.core.rate_limit import limiter   # import from core, not from main

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserOut)
@limiter.limit("5/minute")
def register(request: Request, user_data: UserRegister, db: Session = Depends(get_db)):
    return auth_service.create_user(db, user_data)


@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
def login(request: Request, credentials: UserLogin, db: Session = Depends(get_db)):
    user = auth_service.authenticate_user(db, credentials.email, credentials.password)
    if not user:
        raise CredentialsException()
    token = create_access_token(data={"sub": str(user.id), "email": user.email})
    return Token(access_token=token)