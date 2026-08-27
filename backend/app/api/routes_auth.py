from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.schemas import LoginRequest, TokenResponse
from app.auth.security import create_access_token, verify_password
from app.db.base import get_db
from app.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
    )

    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not user.is_active:
        raise unauthorized

    if not verify_password(payload.password, user.hashed_password):
        raise unauthorized

    token = create_access_token(
        user_id=str(user.id), tenant_id=str(user.tenant_id), role=str(user.role)
    )
    return TokenResponse(access_token=token)
