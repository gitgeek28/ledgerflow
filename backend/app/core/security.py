"""Demo authentication: seeded users, shared demo password, HMAC-signed session token (cookie or Bearer).

This is deliberately simple and documented as demo auth. Roles are enforced server-side on every
state-changing endpoint; it is not an enterprise identity system.
"""
import hmac
import uuid

from fastapi import Depends, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import Forbidden, Unauthorized
from app.db.models import User
from app.db.session import get_db

COOKIE = "lf_session"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key, salt="ledgerflow-session")


def issue_token(user: User) -> str:
    return _serializer().dumps({"uid": str(user.id), "role": user.role})


def check_password(password: str) -> bool:
    return hmac.compare_digest(password.encode(), get_settings().demo_password.encode())


def _token_from(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get(COOKIE)


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _token_from(request)
    if not token:
        raise Unauthorized("Sign in required.")
    try:
        data = _serializer().loads(token, max_age=get_settings().session_ttl_hours * 3600)
    except SignatureExpired as exc:
        raise Unauthorized("Session expired; sign in again.") from exc
    except BadSignature as exc:
        raise Unauthorized("Invalid session.") from exc
    user = db.get(User, uuid.UUID(data["uid"]))
    if not user:
        raise Unauthorized("Unknown user.")
    request.state.user = user
    return user


def require_roles(*roles: str):
    def _dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise Forbidden(f"This action requires one of: {', '.join(r.replace('_', ' ').title() for r in roles)}.")
        return user
    return _dep


OPERATOR = require_roles("AP_ANALYST", "AP_MANAGER")
MANAGER = require_roles("AP_MANAGER")
