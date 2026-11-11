from fastapi import APIRouter, Depends
from pydantic import ValidationError
from sqlalchemy import desc, func, select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import MANAGER, current_user
from app.db.base import utcnow
from app.db.models import Policy, ProcessingRun, User
from app.db.session import get_db
from app.schemas import api
from app.services import audit
from app.services.policy import CATALOGUE, PolicySettings, load_active_policy, settings_to_json

router = APIRouter(prefix="/policies", tags=["policies"])


def _out(db: Session, p: Policy) -> api.PolicyOut:
    by = db.get(User, p.created_by_id) if p.created_by_id else None
    runs = db.scalar(select(func.count()).select_from(ProcessingRun).where(ProcessingRun.policy_id == p.id)) or 0
    out = api.PolicyOut.model_validate(p)
    out.created_by, out.runs_using = (by.name if by else None), runs
    return out


@router.get("", response_model=list[api.PolicyOut])
def list_policies(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return [_out(db, p) for p in db.scalars(select(Policy).order_by(desc(Policy.version)))]


@router.get("/current", response_model=api.PolicyOut)
def current(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return _out(db, load_active_policy(db)[0])


@router.get("/reason-codes")
def reason_codes(_: User = Depends(current_user)):
    return [c.__dict__ for c in CATALOGUE.values()]


@router.post("", response_model=api.PolicyOut, status_code=201)
def create_policy(body: api.PolicyIn, db: Session = Depends(get_db), user: User = Depends(MANAGER)):
    try:
        settings = PolicySettings.model_validate(body.settings)
    except ValidationError as exc:
        raise AppError("Invalid policy settings.", code="VALIDATION_ERROR", status_code=422,
                       details=[{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]) from exc
    active, _ = load_active_policy(db)
    version = (db.scalar(select(func.max(Policy.version))) or 0) + 1
    db.execute(update(Policy).values(is_active=False))
    policy = Policy(version=version, name="Demo AP policy", settings=settings_to_json(settings),
                    change_note=body.change_note, is_active=True, created_by_id=user.id, effective_from=utcnow())
    db.add(policy)
    changed = {k: {"from": active.settings.get(k), "to": v} for k, v in settings_to_json(settings).items()
               if active.settings.get(k) != v}
    audit.record(db, action="POLICY_VERSION_CREATED", actor=user, entity_type="policy", entity_id=str(version),
                 entity_label=f"Policy v{version}", note=body.change_note, before={"version": active.version},
                 after={"version": version, "changes": changed})
    db.commit()
    return _out(db, policy)
