"""Restricted pilot accounts. All identities are verified by Supabase Auth."""

from datetime import timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .account_auth import (
    COOKIE,
    account_session,
    auth_event,
    create_session,
    csrf,
    digest,
    live_tokens,
    provider,
)
from .core import get_db, settings, utcnow
from .models import AccountSession, Membership, Organization
from .security import rate_limit
from . import email_links

router = APIRouter(prefix="/api/v1")
DB = Annotated[Session, Depends(get_db, scope="function")]


class EmailBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        import re

        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value


class PasswordBody(EmailBody):
    password: str = Field(min_length=12, max_length=128)


class VerifyBody(EmailBody):
    token: str = Field(pattern=r"^\d{6,10}$")
    kind: Literal["signup", "recovery"] = "signup"


def profile(account):
    return {
        name: getattr(account, name)
        for name in (
            "id",
            "email",
            "name",
            "job_title",
            "phone",
            "timezone",
            "language",
            "created_at",
            "last_login",
            "onboarding",
            "deletion_requested_at",
        )
    }


def identity_request(request, bucket="identity", limit=8):
    csrf(request)
    rate_limit(request, bucket, limit)
    if not settings.accounts_enabled:
        raise HTTPException(
            503,
            "Private accounts are awaiting identity-provider configuration. Try the fictional demo.",
        )


def admitted(email):
    return email in [
        s.strip().lower() for s in settings.registration_allowlist.split(",") if s.strip()
    ]


@router.get("/auth/config")
def auth_config():
    return {
        "configured": settings.accounts_enabled,
        "registration": settings.accounts_enabled and settings.registration_enabled,
        "google": False,
        "real_uploads": settings.real_uploads_enabled,
        "provider": "Supabase Auth",
        "email_delivery": "provider_configuration_required",
    }


@router.post("/auth/signup")
def signup(body: PasswordBody, request: Request, response: Response, db: DB):
    identity_request(request, "signup", 3)
    if not settings.registration_enabled or not admitted(body.email):
        raise HTTPException(
            403, "Registration is restricted to the operator-approved pilot allowlist."
        )
    challenge = email_links.begin(db, request, response, body.email, "signup")
    result = provider.call(
        "POST",
        "signup?redirect_to=" + quote(settings.app_origin + "/auth/callback", safe=""),
        {
            "email": body.email,
            "password": body.password,
            "code_challenge": challenge,
            "code_challenge_method": "s256",
        },
    )
    # Auto-confirm must never silently become an application session.
    if result.get("access_token"):
        raise HTTPException(
            503, "Email confirmation must be enabled by the identity operator before registration."
        )
    return {
        "status": "verification_required",
        "message": "If your address is eligible, open the verification email link in this same browser. If your provider sends a code, you can enter it instead.",
    }


@router.post("/auth/login")
def login(body: PasswordBody, request: Request, response: Response, db: DB):
    identity_request(request, "login", 8)
    tokens = provider.call("POST", "token?grant_type=password", body.model_dump())
    account = create_session(db, response, tokens, request.cookies.get(COOKIE))
    return {"profile": profile(account)}


@router.post("/auth/verify")
def verify(body: VerifyBody, request: Request, response: Response, db: DB):
    identity_request(request, "verify", 6)
    if body.kind == "signup" and not admitted(body.email):
        raise HTTPException(403, "This address is not admitted to the restricted pilot.")
    tokens = provider.call(
        "POST", "verify", {"email": body.email, "token": body.token, "type": body.kind}
    )
    account = create_session(
        db, response, tokens, request.cookies.get(COOKIE), recovery=body.kind == "recovery"
    )
    email_links.consume(db, request, response)
    return {"profile": profile(account), "recovery": body.kind == "recovery"}


@router.post("/auth/recover")
def recover(body: EmailBody, request: Request, response: Response, db: DB):
    identity_request(request, "recovery", 3)
    # Identical response for every address; no account enumeration via this endpoint.
    if admitted(body.email):
        challenge = email_links.begin(db, request, response, body.email, "recovery")
        try:
            provider.call(
                "POST",
                "recover?redirect_to=" + quote(settings.app_origin + "/auth/callback", safe=""),
                {"email": body.email, "code_challenge": challenge, "code_challenge_method": "s256"},
            )
        except HTTPException as exc:
            if exc.status_code >= 500:
                raise
    return {
        "message": "If an eligible account exists, the identity provider will email a recovery link. Open it in this same browser."
    }


@router.post("/auth/resend")
def resend_verification(body: EmailBody, request: Request):
    identity_request(request, "resend", 3)
    if settings.registration_enabled and admitted(body.email):
        try:
            provider.call("POST", "resend", {"type": "signup", "email": body.email})
        except HTTPException as exc:
            if exc.status_code >= 500:
                raise
    return {
        "message": "If eligible, a fresh verification code will be sent by the identity provider."
    }


class ResetBody(BaseModel):
    password: str = Field(min_length=12, max_length=128)


class CodeExchangeBody(BaseModel):
    code: str = Field(min_length=6, max_length=512)


@router.post("/auth/exchange")
def exchange_email_link(body: CodeExchangeBody, request: Request, response: Response, db: DB):
    identity_request(request, "email-link", 6)
    challenge, verifier = email_links.pending(db, request)
    tokens = provider.exchange(body.code, verifier)
    account = create_session(
        db,
        response,
        tokens,
        request.cookies.get(COOKIE),
        recovery=challenge.kind == "recovery",
        expected_email=challenge.email,
    )
    recovery = challenge.kind == "recovery"
    email_links.consume(db, request, response)
    return {"profile": profile(account), "recovery": recovery}


@router.post("/auth/reset-password")
def reset_password(body: ResetBody, request: Request, response: Response, db: DB):
    account, session = account_session(request, db, allow_recovery=True)
    if not session.recovery or utcnow() - session.created_at.replace(
        tzinfo=session.created_at.tzinfo or utcnow().tzinfo
    ) > timedelta(minutes=10):
        raise HTTPException(403, "A fresh, verified recovery session is required.")
    tokens = live_tokens(db, session)
    provider.call("PUT", "user", {"password": body.password}, access=tokens["access_token"])
    provider.call("POST", "logout?scope=global", access=tokens["access_token"])
    db.execute(delete(AccountSession).where(AccountSession.account_id == account.id))
    auth_event(db, account, "password.recovered")
    response.delete_cookie(
        COOKIE, path="/api/v1", secure=settings.account_cookie_secure, httponly=True, samesite="lax"
    )
    return {"message": "Password updated. All application sessions are revoked. Sign in again."}


@router.post("/auth/logout")
def logout(request: Request, response: Response, db: DB):
    csrf(request)
    # Local revocation succeeds even while the provider is unavailable.
    row = db.get(AccountSession, digest(request.cookies.get(COOKIE, "")))
    provider_revoked = False
    if row:
        from .account_auth import decrypted

        try:
            provider.call(
                "POST", "logout?scope=local", access=decrypted(row.provider_tokens)["access_token"]
            )
            provider_revoked = True
        except HTTPException:
            pass
        from .models import Account

        auth_event(db, db.get(Account, row.account_id), "session.revoked")
        db.delete(row)
    response.delete_cookie(
        COOKIE, path="/api/v1", secure=settings.account_cookie_secure, httponly=True, samesite="lax"
    )
    return {"revoked": True, "provider_revoked": provider_revoked}


@router.get("/account/profile")
def get_profile(request: Request, db: DB):
    account, _ = account_session(request, db, allow_recovery=True)
    return profile(account)


class ProfileBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    job_title: str = Field(default="", max_length=100)
    phone: str = Field(default="", max_length=30, pattern=r"^[0-9+() .-]*$")
    timezone: str = Field(default="Asia/Kolkata", max_length=80)
    language: Literal["en"] = "en"

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Choose a valid IANA timezone") from exc
        return value

    @field_validator("name", "job_title")
    @classmethod
    def trim(cls, value):
        if not value.strip() and value:
            raise ValueError("Use visible text")
        return value.strip()


@router.patch("/account/profile")
def edit_profile(body: ProfileBody, request: Request, db: DB):
    account, _ = account_session(request, db)
    for key, value in body.model_dump().items():
        setattr(account, key, value)
    auth_event(db, account, "profile.updated")
    return profile(account)


@router.get("/account/sessions")
def sessions(request: Request, db: DB):
    account, current = account_session(request, db)
    return [
        {
            "id": row.digest[:16],
            "current": row.digest == current.digest,
            "created_at": row.created_at,
            "expires_at": row.expires_at,
        }
        for row in db.scalars(
            select(AccountSession).where(
                AccountSession.account_id == account.id, AccountSession.expires_at > utcnow()
            )
        )
    ]


@router.post("/account/sessions/revoke-others")
def revoke_others(request: Request, db: DB):
    account, session = account_session(request, db)
    db.execute(
        delete(AccountSession).where(
            AccountSession.account_id == account.id, AccountSession.digest != session.digest
        )
    )
    auth_event(db, account, "sessions.others_revoked")
    return {"revoked": True}


class ChangePasswordBody(ResetBody):
    current_password: str = Field(min_length=1, max_length=128)


@router.post("/account/password")
def change_password(body: ChangePasswordBody, request: Request, response: Response, db: DB):
    account, session = account_session(request, db)
    rate_limit(request, "password-change", 3)
    reauth = provider.call(
        "POST",
        "token?grant_type=password",
        {"email": account.email, "password": body.current_password},
    )
    provider.call("PUT", "user", {"password": body.password}, access=reauth["access_token"])
    provider.call("POST", "logout?scope=global", access=reauth["access_token"])
    db.execute(delete(AccountSession).where(AccountSession.account_id == account.id))
    auth_event(db, account, "password.changed")
    response.delete_cookie(COOKIE, path="/api/v1")
    return {"message": "Password changed. Sign in again on all devices."}


@router.post("/account/email")
def change_email(body: EmailBody, request: Request, db: DB):
    account, session = account_session(request, db)
    rate_limit(request, "email-change", 3)
    if not admitted(body.email):
        raise HTTPException(403, "The new email must also be approved for the restricted pilot.")
    provider.call(
        "PUT",
        "user?redirect_to=" + quote(settings.app_origin + "/auth/callback", safe=""),
        {"email": body.email},
        access=live_tokens(db, session)["access_token"],
    )
    auth_event(db, account, "email.change_requested")
    return {
        "message": "Confirm the change using the identity provider's verification email. Your account email changes only after provider verification and a new sign-in."
    }


class EmailChangeVerifyBody(EmailBody):
    token: str = Field(pattern=r"^\d{6,10}$")


@router.post("/account/email/verify")
def verify_email_change(body: EmailChangeVerifyBody, request: Request, response: Response, db: DB):
    account, _ = account_session(request, db)
    rate_limit(request, "verify-email-change", 6)
    if not admitted(body.email):
        raise HTTPException(403, "The address must be admitted to the restricted pilot.")
    result = provider.call(
        "POST", "verify", {"email": body.email, "token": body.token, "type": "email_change"}
    )
    if result.get("access_token"):
        identity = provider.call("GET", "user", access=result["access_token"])
        if identity.get("id") != account.provider_id:
            raise HTTPException(403, "Email verification belongs to another identity.")
        create_session(db, response, result, request.cookies.get(COOKIE))
        auth_event(db, account, "email.change_verified")
    return {
        "message": "Verification processed by the provider. Secure email change may require codes from both addresses. Your local email updates only after the provider confirms the change."
    }


class DeleteBody(EmailBody):
    confirmation: Literal["REQUEST DELETION"]


@router.post("/account/deletion-request")
def deletion_request(body: DeleteBody, request: Request, response: Response, db: DB):
    account, session = account_session(request, db)
    if body.email != account.email:
        raise HTTPException(422, "Confirm your current account email.")
    members = list(
        db.scalars(
            select(Membership).where(
                Membership.account_id == account.id, Membership.active.is_(True)
            )
        )
    )
    for member in members:
        org = db.scalar(
            select(Organization).where(Organization.id == member.org_id).with_for_update()
        )
        owners = db.scalar(
            select(func.count())
            .select_from(Membership)
            .where(
                Membership.org_id == member.org_id,
                Membership.role == "owner",
                Membership.active.is_(True),
            )
        )
        if member.role == "owner" and owners <= 1 and not org.settings.get("_closed_at"):
            raise HTTPException(
                409, "Transfer ownership or close your organization before requesting deletion."
            )
    account.deletion_requested_at = utcnow()
    for member in members:
        member.active = False
    try:
        provider.call(
            "POST", "logout?scope=global", access=live_tokens(db, session)["access_token"]
        )
    except HTTPException:
        pass
    db.execute(delete(AccountSession).where(AccountSession.account_id == account.id))
    auth_event(db, account, "account.deletion_requested")
    response.delete_cookie(COOKIE, path="/api/v1")
    return {
        "status": "pending_operator_review",
        "message": "Access revoked. Business records are retained; deletion requires operator review under the documented retention policy.",
    }
