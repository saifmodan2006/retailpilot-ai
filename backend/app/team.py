"""Single-use, email-bound invitations. No unconfigured delivery claims."""

import secrets
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from .account_auth import account_session, aware, digest
from .accounts import DB, EmailBody
from .core import settings, utcnow
from .models import Account, Invitation, Membership, User
from .organizations import actor, guard_final_owner, selected
from .security import rate_limit
from .workflows import audit

router = APIRouter(prefix="/api/v1")


def invite_info(row):
    if row.status == "pending" and aware(row.expires_at) <= utcnow():
        row.status = "expired"
    return {
        key: getattr(row, key)
        for key in ("id", "email", "role", "status", "delivery", "created_at", "expires_at")
    }


@router.get("/organizations/current/team")
def team(request: Request, db: DB):
    _, _, org, current = selected(request, db, ("owner", "admin"))
    return {
        "your_role": current.role,
        "your_membership": current.id,
        "members": [
            {
                "id": member.id,
                "name": account.name,
                "email": account.email,
                "role": member.role,
                "joined_at": member.created_at,
            }
            for member, account in db.execute(
                select(Membership, Account)
                .join(Account)
                .where(Membership.org_id == org.id, Membership.active.is_(True))
            )
        ],
        "invitations": [
            invite_info(row)
            for row in db.scalars(select(Invitation).where(Invitation.org_id == org.id))
        ],
        "email_delivery": "not_configured",
    }


class InviteBody(EmailBody):
    role: Literal["admin", "manager", "analyst", "viewer"] = "viewer"


@router.post("/organizations/current/invitations")
def invite(body: InviteBody, request: Request, db: DB):
    account, _, org, current = selected(request, db, ("owner", "admin"))
    rate_limit(request, "invite:" + account.id, 5)
    if current.role != "owner" and body.role == "admin":
        raise HTTPException(403, "Only an owner can invite an administrator.")
    if db.scalar(
        select(Membership.id)
        .join(Account)
        .where(
            Membership.org_id == org.id, Membership.active.is_(True), Account.email == body.email
        )
    ):
        raise HTTPException(409, "This address already has an active membership.")
    if (
        db.scalar(
            select(func.count())
            .select_from(Membership)
            .where(Membership.org_id == org.id, Membership.active.is_(True))
        )
        >= 10
    ):
        raise HTTPException(429, "Pilot workspaces support at most ten active members.")
    row = db.scalar(
        select(Invitation).where(Invitation.org_id == org.id, Invitation.email == body.email)
    )
    if (
        not row
        and db.scalar(
            select(func.count()).select_from(Invitation).where(Invitation.org_id == org.id)
        )
        >= 20
    ):
        raise HTTPException(429, "Pilot workspaces support at most twenty invitation addresses.")
    secret = secrets.token_urlsafe(32)
    values = {
        "role": body.role,
        "token_digest": digest(secret),
        "status": "pending",
        "delivery": "not_delivered",
        "invited_by": account.id,
        "expires_at": utcnow() + timedelta(hours=24),
    }
    if row:
        for key, value in values.items():
            setattr(row, key, value)
    else:
        row = Invitation(org_id=org.id, email=body.email, **values)
        db.add(row)
    db.flush()
    audit(
        db,
        actor(db, current),
        "invitation.created",
        row.id,
        {"role": row.role, "delivery": row.delivery},
    )
    # The link is revealed once, only to the authorized issuer. Fragment avoids server URL logs.
    return {
        **invite_info(row),
        "accept_url": settings.app_origin + "/auth/invitation#token=" + secret,
        "message": "Invitation pending. Email was NOT sent: transactional delivery is not configured. Share this single-use link securely with the named recipient; the operator must also admit their email to the private pilot.",
    }


@router.post("/organizations/current/invitations/{ident}/revoke")
def revoke_invitation(ident: int, request: Request, db: DB):
    _, _, org, current = selected(request, db, ("owner", "admin"))
    row = db.scalar(
        select(Invitation)
        .where(Invitation.id == ident, Invitation.org_id == org.id)
        .with_for_update()
    )
    if not row:
        raise HTTPException(404, "Invitation not found")
    if current.role != "owner" and row.role == "admin":
        raise HTTPException(403, "Only an owner can revoke an administrator invitation.")
    if invite_info(row)["status"] != "pending":
        raise HTTPException(409, "Only pending invitations can be revoked.")
    row.status = "revoked"
    audit(db, actor(db, current), "invitation.revoked", row.id)
    return invite_info(row)


class RespondBody(BaseModel):
    token: str = Field(min_length=40, max_length=64)
    decision: Literal["accept", "reject"]


@router.post("/invitations/respond")
def respond(body: RespondBody, request: Request, db: DB):
    account, session = account_session(request, db)
    rate_limit(request, "invite-response:" + account.id, 10)
    row = db.scalar(
        select(Invitation).where(Invitation.token_digest == digest(body.token)).with_for_update()
    )
    if not row or row.email != account.email:
        raise HTTPException(404, "Invitation not available for this verified account.")
    if invite_info(row)["status"] != "pending":
        raise HTTPException(409, "Invitation expired, revoked or already used.")
    from .models import Organization

    org = db.scalar(select(Organization).where(Organization.id == row.org_id).with_for_update())
    if not org or org.is_demo or org.settings.get("_closed_at"):
        raise HTTPException(403, "The workspace is not available.")
    issuer = db.scalar(
        select(Membership).where(
            Membership.org_id == org.id,
            Membership.account_id == row.invited_by,
            Membership.active.is_(True),
        )
    )
    if (
        not issuer
        or issuer.role not in ("owner", "admin")
        or (row.role == "admin" and issuer.role != "owner")
    ):
        raise HTTPException(
            403, "The invitation issuer no longer has permission. Request a fresh invitation."
        )
    if body.decision == "reject":
        row.status = "rejected"
        from .models import AuditEvent

        db.add(
            AuditEvent(
                org_id=org.id,
                actor="Verified invitee " + account.id,
                action="invitation.rejected",
                entity=str(row.id),
                detail={"account_id": account.id},
            )
        )
        return {"status": row.status}
    if (
        db.scalar(
            select(func.count())
            .select_from(Membership)
            .where(Membership.org_id == org.id, Membership.active.is_(True))
        )
        >= 10
    ):
        raise HTTPException(429, "The workspace is at member capacity.")
    member = db.scalar(
        select(Membership).where(Membership.org_id == org.id, Membership.account_id == account.id)
    )
    if member and member.active:
        raise HTTPException(409, "You already have an active membership.")
    if not member:
        user = User(org_id=org.id, name=account.name or account.email, role=row.role)
        db.add(user)
        db.flush()
        member = Membership(org_id=org.id, account_id=account.id, actor_id=user.id, role=row.role)
        db.add(member)
    else:
        member.active, member.role = True, row.role
    row.status, session.org_id = "accepted", org.id
    account.onboarding = {**account.onboarding, "completed": True, "joined_by_invitation": True}
    audit(
        db,
        actor(db, member),
        "membership.invitation_accepted",
        row.id,
        {"role": row.role, "account_id": account.id, "invited_by": row.invited_by},
    )
    return {"status": row.status, "organization_id": org.id}


class RoleBody(BaseModel):
    role: Literal["owner", "admin", "manager", "analyst", "viewer"]


def target_member(db, ident, org, current, next_role=None):
    target = db.scalar(
        select(Membership)
        .where(Membership.id == ident, Membership.org_id == org.id, Membership.active.is_(True))
        .with_for_update()
    )
    if not target:
        raise HTTPException(404, "Member not found")
    if current.role != "owner" and (
        target.role in ("owner", "admin") or next_role in ("owner", "admin")
    ):
        raise HTTPException(
            403, "Administrators can manage only manager, analyst and viewer memberships."
        )
    guard_final_owner(db, target, next_role, removing=next_role is None)
    return target


@router.patch("/organizations/current/team/{ident}")
def change_role(ident: int, body: RoleBody, request: Request, db: DB):
    _, _, org, current = selected(request, db, ("owner", "admin"))
    target = target_member(db, ident, org, current, body.role)
    previous, target.role = target.role, body.role
    audit(
        db,
        actor(db, current),
        "membership.role_changed",
        target.id,
        {"previous": previous, "role": body.role},
    )
    return {"id": target.id, "role": target.role}


@router.post("/organizations/current/team/{ident}/remove")
def remove_member(ident: int, request: Request, db: DB):
    _, _, org, current = selected(request, db, ("owner", "admin"))
    target = target_member(db, ident, org, current)
    target.active = False
    audit(db, actor(db, current), "membership.removed", target.id)
    return {"removed": True}
