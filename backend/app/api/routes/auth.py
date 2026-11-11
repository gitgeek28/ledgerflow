from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import Unauthorized
from app.core.security import COOKIE, check_password, current_user, issue_token
from app.db.models import User
from app.db.session import get_db
from app.schemas.api import LoginIn, LoginOut, UserOut
from app.services import audit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/demo-users", response_model=list[UserOut])
def demo_users(db: Session = Depends(get_db)):
    """Seeded fictional users for the demo sign-in screen."""
    return db.scalars(select(User).order_by(User.role, User.name)).all()


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if not user or not check_password(body.password):
        raise Unauthorized("Email or password is incorrect.")
    token = issue_token(user)
    s = get_settings()
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax", secure=s.cookie_secure,
                        max_age=s.session_ttl_hours * 3600, path="/")
    audit.record(db, action="SIGN_IN", actor=user, entity_type="user", entity_id=str(user.id),
                 entity_label=user.email)
    db.commit()
    return LoginOut(user=UserOut.model_validate(user), token=token)


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user
