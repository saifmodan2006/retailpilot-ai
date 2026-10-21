"""Organization lifecycle: membership is checked against Neon on every request."""

import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import func, select

from .account_auth import account_session
from .accounts import DB, ProfileBody
from .core import settings, utcnow
from .models import Account, Membership, Organization, Store, User
from .workflows import audit

router = APIRouter(prefix="/api/v1")
ROLES = ("owner", "admin", "manager", "analyst", "viewer")


def selected(request, db, roles=ROLES):
    account, session = account_session(request, db)
    org = db.scalar(select(Organization).where(Organization.id == session.org_id).with_for_update())
    member = db.scalar(
        select(Membership).where(
            Membership.account_id == account.id,
            Membership.org_id == session.org_id,
            Membership.active.is_(True),
        )
    )
    if (
        not org
        or org.is_demo
        or org.settings.get("_closed_at")
        or not member
        or member.role not in roles
    ):
        raise HTTPException(
            403, "An active workspace membership with the required permission is necessary."
        )
    return account, session, org, member


def actor(db, membership):
    user = db.get(User, membership.actor_id)
    account = db.get(Account, membership.account_id)
    user.role = membership.role
    user.name = account.name or account.email
    return user


def org_info(db, org, member):
    return {
        "id": org.id,
        "name": org.name,
        "created_at": org.created_at,
        "role": member.role,
        "data_mode": "synthetic" if org.settings.get("_synthetic") else "private",
        "settings": {k: v for k, v in org.settings.items() if not k.startswith("_")},
        "owners": list(
            db.scalars(
                select(Membership.account_id).where(
                    Membership.org_id == org.id,
                    Membership.role == "owner",
                    Membership.active.is_(True),
                )
            )
        ),
        "closed": bool(org.settings.get("_closed_at")),
    }


class StoreBody(BaseModel):
    code: str = Field(min_length=1, max_length=24, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=100)
    city: str = Field(default="", max_length=100)


class OrganizationBody(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    business_type: str = Field(default="Retail", max_length=80)
    industry: str = Field(default="Retail", max_length=80)
    country: str = Field(default="IN", pattern=r"^[A-Z]{2}$")
    currency: Literal["INR", "USD", "EUR", "GBP"] = "INR"
    timezone: str = Field(default="Asia/Kolkata", max_length=80)
    workspace_name: str = Field(default="Main workspace", min_length=1, max_length=100)
    safety_days: int = Field(default=7, ge=0, le=60)
    dead_days: int = Field(default=90, ge=30, le=365)
    cover_days: int = Field(default=14, ge=1, le=90)
    reporting_week_start: Literal["Monday", "Sunday"] = "Monday"
    analyst_imports_enabled: bool = False

    _timezone = field_validator("timezone")(ProfileBody.valid_timezone.__func__)

    @field_validator("name", "workspace_name")
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError("A visible name is required")
        return value.strip()


class OnboardingBody(BaseModel):
    step: int = Field(ge=0, le=3)
    business: OrganizationBody
    stores: list[StoreBody] = Field(default_factory=list, max_length=5)
    start: Literal["empty", "synthetic", "upload"] = "empty"


def create_org(db, account, body, stores):
    db.scalar(select(Account).where(Account.id == account.id).with_for_update())
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy import text

        db.execute(text("SELECT pg_advisory_xact_lock(7319286)"))
    if (
        db.scalar(
            select(func.count()).select_from(Organization).where(Organization.is_demo.is_(False))
        )
        >= settings.account_max_organizations
    ):
        raise HTTPException(429, "The private pilot is at workspace capacity.")
    if (
        db.scalar(
            select(func.count())
            .select_from(Membership)
            .where(
                Membership.account_id == account.id,
                Membership.role == "owner",
                Membership.active.is_(True),
            )
        )
        >= 2
    ):
        raise HTTPException(429, "Each pilot account can own at most two workspaces.")
    if len(set(s.code for s in stores)) != len(stores):
        raise HTTPException(422, "Store codes must be unique within the workspace.")
    values = body.model_dump()
    org = Organization(
        id=str(uuid.uuid4()), name=values.pop("name"), is_demo=False, settings=values
    )
    db.add(org)
    db.flush()
    user = User(org_id=org.id, name=account.name or account.email, role="owner")
    db.add(user)
    db.flush()
    member = Membership(org_id=org.id, account_id=account.id, actor_id=user.id, role="owner")
    db.add(member)
    db.add_all(Store(org_id=org.id, **s.model_dump()) for s in stores)
    db.flush()
    audit(db, user, "organization.created", org.id)
    return org, member


@router.get("/organizations")
def organizations(request: Request, db: DB):
    account, session = account_session(request, db)
    return {
        "selected": session.org_id,
        "organizations": [
            org_info(db, org, member)
            for org, member in db.execute(
                select(Organization, Membership)
                .join(Membership, Membership.org_id == Organization.id)
                .where(
                    Membership.account_id == account.id,
                    Membership.active.is_(True),
                    Organization.is_demo.is_(False),
                )
            )
        ],
    }


@router.post("/organizations")
def new_organization(body: OrganizationBody, request: Request, db: DB):
    account, session = account_session(request, db)
    org, member = create_org(db, account, body, [])
    session.org_id = org.id
    account.onboarding = {**account.onboarding, "last_organization_id": org.id}
    return org_info(db, org, member)


class SelectBody(BaseModel):
    organization_id: str = Field(max_length=36)


@router.post("/organizations/select")
def select_organization(body: SelectBody, request: Request, db: DB):
    account, session = account_session(request, db)
    member = db.scalar(
        select(Membership).where(
            Membership.account_id == account.id,
            Membership.org_id == body.organization_id,
            Membership.active.is_(True),
        )
    )
    org = db.get(Organization, body.organization_id)
    if not member or not org or org.is_demo or org.settings.get("_closed_at"):
        raise HTTPException(403, "This workspace is not available to your account.")
    session.org_id = org.id
    account.onboarding = {**account.onboarding, "last_organization_id": org.id}
    audit(db, actor(db, member), "workspace.selected", org.id)
    return org_info(db, org, member)


@router.get("/organizations/current")
def current_organization(request: Request, db: DB):
    _, _, org, member = selected(request, db)
    return org_info(db, org, member)


@router.patch("/organizations/current")
def edit_organization(body: OrganizationBody, request: Request, db: DB):
    _, _, org, member = selected(request, db, ("owner", "admin"))
    values = body.model_dump()
    from .models import SKU

    planning_changed = any(
        values[key] != org.settings.get(key) for key in ("safety_days", "dead_days", "cover_days")
    )

    if body.currency != org.settings.get("currency", "INR") and db.scalar(
        select(SKU.id).where(SKU.org_id == org.id)
    ):
        raise HTTPException(
            409,
            "Currency cannot be relabeled after business data exists. No currency conversion is implemented.",
        )
    org.name = values.pop("name")
    # Retain operational/security metadata; planning API uses this same dictionary.
    org.settings = {**org.settings, **values}
    if planning_changed:
        from .models import Recommendation
        from .workflows import recommendations

        db.query(Recommendation).filter(
            Recommendation.org_id == org.id, Recommendation.status == "Suggested"
        ).delete()
        recommendations(db, org.id, org.settings)
    audit(db, actor(db, member), "organization.updated", org.id)
    return org_info(db, org, member)


@router.post("/organizations/current/stores")
def add_store(body: StoreBody, request: Request, db: DB):
    _, _, org, member = selected(request, db, ("owner", "admin"))
    if db.scalar(select(func.count()).select_from(Store).where(Store.org_id == org.id)) >= 20:
        raise HTTPException(429, "Pilot workspaces support at most 20 stores.")
    row = Store(org_id=org.id, **body.model_dump())
    db.add(row)
    db.flush()
    audit(db, actor(db, member), "store.created", row.id)
    return {"id": row.id, **body.model_dump()}


@router.patch("/organizations/current/stores/{ident}")
def edit_store(ident: int, body: StoreBody, request: Request, db: DB):
    _, _, org, member = selected(request, db, ("owner", "admin"))
    row = db.scalar(select(Store).where(Store.id == ident, Store.org_id == org.id))
    if not row:
        raise HTTPException(404, "Store not found")
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    audit(db, actor(db, member), "store.updated", row.id)
    return {"id": row.id, **body.model_dump()}


def guard_final_owner(db, member, next_role=None, removing=False):
    if member.role == "owner" and (removing or next_role != "owner"):
        count = db.scalar(
            select(func.count())
            .select_from(Membership)
            .where(
                Membership.org_id == member.org_id,
                Membership.role == "owner",
                Membership.active.is_(True),
            )
        )
        if count <= 1:
            raise HTTPException(
                409, "The final owner cannot leave or lose ownership. Transfer ownership first."
            )


@router.post("/organizations/current/leave")
def leave_organization(request: Request, db: DB):
    _, session, org, member = selected(request, db)
    guard_final_owner(db, member, removing=True)
    member.active = False
    session.org_id = None
    audit(db, actor(db, member), "membership.left", member.id)
    return {"left": True}


class CloseBody(BaseModel):
    confirmation: str = Field(max_length=120)


@router.post("/organizations/current/close")
def close_organization(body: CloseBody, request: Request, db: DB):
    _, session, org, member = selected(request, db, ("owner",))
    if body.confirmation != org.name:
        raise HTTPException(422, "Enter the exact organization name to confirm closure.")
    from .models import Workflow

    if db.scalar(
        select(Workflow.id).where(
            Workflow.org_id == org.id, Workflow.status.in_(["Running", "Pending"])
        )
    ):
        raise HTTPException(409, "Wait for active workflows to finish before closure.")
    org.settings = {**org.settings, "_closed_at": utcnow().isoformat()}
    session.org_id = None
    audit(db, actor(db, member), "organization.closed", org.id)
    return {
        "status": "closed",
        "message": "Workspace access is closed. Records are retained for operator review; no business data was deleted.",
    }


@router.get("/onboarding")
def get_onboarding(request: Request, db: DB):
    account, _ = account_session(request, db)
    return account.onboarding


@router.patch("/onboarding")
def save_onboarding(body: OnboardingBody, request: Request, db: DB):
    account, _ = account_session(request, db)
    if account.onboarding.get("completed"):
        raise HTTPException(
            409, "Initial onboarding is complete. Use workspace settings for changes."
        )
    account.onboarding = body.model_dump()
    return account.onboarding


@router.post("/onboarding/complete")
def complete_onboarding(request: Request, db: DB):
    account, session = account_session(request, db)
    db.scalar(select(Account).where(Account.id == account.id).with_for_update())
    if account.onboarding.get("completed"):
        return account.onboarding
    try:
        draft = OnboardingBody.model_validate(account.onboarding)
    except ValidationError as exc:
        raise HTTPException(422, "Save the onboarding steps before completing setup.") from exc
    if not account.name:
        raise HTTPException(422, "Save your personal details before completing onboarding.")
    if draft.step != 3:
        raise HTTPException(422, "Complete all onboarding steps first.")
    # Fictional seeding is explicit, separate and bounded; never block signup on a large seed.
    org, _ = create_org(
        db, account, draft.business, [] if draft.start == "synthetic" else draft.stores
    )
    session.org_id = org.id
    account.onboarding = {**account.onboarding, "last_organization_id": org.id}
    account.onboarding = {**account.onboarding, "completed": True, "organization_id": org.id}
    return account.onboarding


@router.post("/organizations/current/sample-data")
def sample_data(request: Request, db: DB):
    _, _, org, member = selected(request, db, ("owner", "admin"))
    from .models import Sale, Product
    from .seed import seed
    from .workflows import recommendations

    if db.scalar(select(Store.id).where(Store.org_id == org.id)) or db.scalar(
        select(Product.id).where(Product.org_id == org.id)
    ):
        raise HTTPException(
            409,
            "Fictional samples require a completely empty workspace so real and synthetic records are never mixed.",
        )
    if db.scalar(select(func.count()).select_from(Sale)) + 97608 > 400000:
        raise HTTPException(
            429, "Shared free-tier storage budget reached. Open an empty workspace instead."
        )
    if org.settings.get("currency", "INR") != "INR":
        raise HTTPException(409, "The fictional sample uses INR. Select INR before loading it.")
    result = seed(db, org.id)
    from .capacity import storage_budget

    storage_budget(db)
    recommendations(db, org.id, org.settings)
    org.settings = {**org.settings, "_synthetic": True}
    audit(db, actor(db, member), "sample.loaded", org.id, result)
    return result
