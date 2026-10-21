"""Managed identity adapter and server-only opaque account sessions.

No provider access/refresh token is returned to JavaScript. Supabase owns all
password, verification and recovery token cryptography. No service-role key.
"""

import hashlib
import json
import secrets
import uuid
from datetime import timedelta, timezone

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, Request, Response
from sqlalchemy import delete, func, select

from .core import settings, utcnow
from .models import Account, AccountSession, AuthenticationEvent, Membership, Organization, User

COOKIE = "rp-account"


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def aware(value):
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def csrf(request: Request):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        if (
            request.headers.get("origin") != settings.app_origin
            or request.headers.get("x-rp-csrf") != "1"
        ):
            raise HTTPException(
                403, "This action requires the trusted application origin and CSRF header"
            )


class SupabaseIdentity:
    def exchange(self, code, verifier):
        from supabase_auth import SyncGoTrueClient
        from supabase_auth.errors import AuthError

        try:
            with httpx.Client(timeout=15, follow_redirects=False) as transport:
                client = SyncGoTrueClient(
                    url=settings.supabase_url.rstrip("/") + "/auth/v1",
                    headers={"apikey": settings.supabase_publishable_key},
                    http_client=transport,
                    persist_session=False,
                    auto_refresh_token=False,
                    flow_type="pkce",
                )
                result = client.exchange_code_for_session(
                    {"auth_code": code, "code_verifier": verifier}
                )
                if not result.session:
                    raise HTTPException(
                        401, "The identity provider did not establish a verified session."
                    )
                return result.session.model_dump(mode="json")
        except (AuthError, httpx.HTTPError) as exc:
            raise HTTPException(
                401,
                "The verification link is invalid, expired or already used. Request a fresh email.",
            ) from exc

    def call(self, method, path, body=None, access=None):
        if not settings.accounts_enabled:
            raise HTTPException(
                503, "Private accounts are not configured. The fictional demo remains available."
            )
        headers = {"apikey": settings.supabase_publishable_key}
        if access:
            headers["Authorization"] = "Bearer " + access
        try:
            with httpx.Client(timeout=15, follow_redirects=False) as client:
                result = client.request(
                    method,
                    settings.supabase_url.rstrip("/") + "/auth/v1/" + path,
                    headers=headers,
                    json=body,
                )
        except httpx.HTTPError as exc:
            raise HTTPException(
                503, "Identity service temporarily unavailable. Please retry."
            ) from exc
        if not result.is_success:
            # Provider errors can reveal account existence or internal configuration.
            raise HTTPException(
                401 if result.status_code < 500 else 503,
                "Identity request could not be completed. Check the details or request a fresh verification code.",
            )
        return result.json() if result.content else {}


provider = SupabaseIdentity()


def encrypted(tokens):
    tokens = {
        **tokens,
        "expires_at": tokens.get(
            "expires_at", utcnow().timestamp() + tokens.get("expires_in", 300)
        ),
    }
    return (
        Fernet(settings.session_encryption_key.encode())
        .encrypt(json.dumps(tokens).encode())
        .decode()
    )


def decrypted(value):
    try:
        return json.loads(Fernet(settings.session_encryption_key.encode()).decrypt(value.encode()))
    except (InvalidToken, ValueError, TypeError) as exc:
        raise HTTPException(401, "Session unavailable. Sign in again.") from exc


def auth_event(db, account, action):
    db.add(AuthenticationEvent(account_id=account.id if account else None, action=action))
    old = list(
        db.scalars(
            select(AuthenticationEvent.id).order_by(AuthenticationEvent.id.desc()).offset(1000)
        )
    )
    if old:
        db.execute(delete(AuthenticationEvent).where(AuthenticationEvent.id.in_(old)))


def set_cookie(response: Response, secret):
    response.set_cookie(
        COOKIE,
        secret,
        max_age=8 * 3600,
        httponly=True,
        secure=settings.account_cookie_secure,
        samesite="lax",
        path="/api/v1",
    )


def create_session(db, response, tokens, previous=None, recovery=False, expected_email=None):
    identity = provider.call("GET", "user", access=tokens["access_token"])
    if not identity.get("email_confirmed_at") or not identity.get("email"):
        raise HTTPException(403, "Verify your email before accessing a private workspace.")
    if expected_email and identity["email"].lower() != expected_email:
        raise HTTPException(403, "The verification link belongs to a different email.")
    account = db.scalar(
        select(Account).where(Account.provider_id == identity["id"]).with_for_update()
    )
    if not account:
        # Serialize admission on PostgreSQL, preventing cap races between identities.
        if db.bind.dialect.name == "postgresql":
            from sqlalchemy import text

            db.execute(text("SELECT pg_advisory_xact_lock(7319285)"))
        if db.scalar(select(func.count()).select_from(Account)) >= settings.account_max_users:
            raise HTTPException(429, "The private pilot is at account capacity.")
        if identity["email"].lower() not in [
            e.strip().lower() for e in settings.registration_allowlist.split(",") if e.strip()
        ]:
            raise HTTPException(403, "This account is not admitted to the restricted pilot.")
        account = Account(
            id=str(uuid.uuid4()), provider_id=identity["id"], email=identity["email"].lower()
        )
        db.add(account)
        db.flush()
    if account.deletion_requested_at:
        raise HTTPException(403, "Account deletion is pending. Contact the application operator.")
    account.email = identity["email"].lower()
    account.last_login = utcnow()
    db.execute(delete(AccountSession).where(AccountSession.expires_at <= utcnow()))
    if previous:
        db.execute(delete(AccountSession).where(AccountSession.digest == digest(previous)))
    existing = list(
        db.scalars(
            select(AccountSession)
            .where(AccountSession.account_id == account.id)
            .order_by(AccountSession.created_at.desc())
        )
    )
    for old in existing[4:]:
        db.delete(old)
    # Keep audit retention bounded; events contain action/identity IDs, never credentials.
    old_events = list(
        db.scalars(
            select(AuthenticationEvent.id).order_by(AuthenticationEvent.id.desc()).offset(1000)
        )
    )
    if old_events:
        db.execute(delete(AuthenticationEvent).where(AuthenticationEvent.id.in_(old_events)))
    available = [
        org
        for org in db.scalars(
            select(Organization)
            .join(Membership)
            .where(
                Membership.account_id == account.id,
                Membership.active.is_(True),
                Organization.is_demo.is_(False),
            )
        )
        if not org.settings.get("_closed_at")
    ]
    selected = next(
        (org.id for org in available if org.id == account.onboarding.get("last_organization_id")),
        available[0].id if available else None,
    )
    secret = secrets.token_urlsafe(32)
    db.add(
        AccountSession(
            digest=digest(secret),
            account_id=account.id,
            org_id=selected,
            provider_tokens=encrypted(tokens),
            recovery=recovery,
            expires_at=utcnow() + timedelta(hours=8),
        )
    )
    auth_event(db, account, "recovery.verified" if recovery else "session.created")
    set_cookie(response, secret)
    return account


def account_session(request: Request, db, allow_recovery=False):
    if not settings.accounts_enabled:
        raise HTTPException(503, "Private accounts are not configured. Try the fictional demo.")
    csrf(request)
    secret = request.cookies.get(COOKIE, "")
    row = db.scalar(
        select(AccountSession).where(AccountSession.digest == digest(secret)).with_for_update()
    )
    if not row or aware(row.expires_at) <= utcnow():
        raise HTTPException(401, "Your account session expired. Sign in again.")
    account = db.get(Account, row.account_id)
    if not account or account.deletion_requested_at:
        raise HTTPException(401, "Account access has been revoked.")
    if row.recovery and not allow_recovery:
        raise HTTPException(403, "Complete password recovery before continuing.")
    from .security import rate_limit

    rate_limit(request, "account:" + account.id, 120)
    tokens = live_tokens(db, row)
    identity = provider.call("GET", "user", access=tokens["access_token"])
    if identity.get("id") != account.provider_id or not identity.get("email_confirmed_at"):
        raise HTTPException(401, "Identity verification failed.")
    verified_email = identity.get("email", "").lower()
    if verified_email not in [
        email.strip().lower()
        for email in settings.registration_allowlist.split(",")
        if email.strip()
    ]:
        raise HTTPException(403, "This verified email is not admitted to the restricted pilot.")
    if verified_email != account.email:
        account.email = verified_email
        auth_event(db, account, "identity.email_synchronized")
    return account, row


def live_tokens(db, session):
    tokens = decrypted(session.provider_tokens)
    if tokens.get("expires_at", 0) <= utcnow().timestamp() + 30:
        fresh = provider.call(
            "POST", "token?grant_type=refresh_token", {"refresh_token": tokens["refresh_token"]}
        )
        session.provider_tokens = encrypted(fresh)
        # Commit rotation before a subsequent business validation can roll back.
        db.commit()
        tokens = fresh
    return tokens


def persistent_actor(request, db):
    account, session = account_session(request, db)
    member = db.scalar(
        select(Membership).where(
            Membership.account_id == account.id,
            Membership.org_id == session.org_id,
            Membership.active.is_(True),
        )
    )
    org = db.get(Organization, session.org_id) if session.org_id else None
    if not member or not org or org.is_demo or org.settings.get("_closed_at"):
        raise HTTPException(403, "Select an active workspace where you have a current membership.")
    actor = db.get(User, member.actor_id)
    if not actor or actor.org_id != org.id:
        raise HTTPException(403, "Workspace actor is unavailable.")
    actor.role, actor.name = member.role, account.name or account.email
    from .retention import maintain_workspace

    maintain_workspace(db, org)
    if member.role == "viewer" and request.method not in ("GET", "HEAD", "OPTIONS"):
        raise HTTPException(403, "Viewer access is read-only.")
    if (
        member.role == "analyst"
        and request.method not in ("GET", "HEAD", "OPTIONS")
        and request.url.path.startswith("/api/v1/imports")
        and not org.settings.get("analyst_imports_enabled", False)
    ):
        raise HTTPException(
            403, "An owner or administrator must authorize analyst imports in workspace settings."
        )
    if request.url.path.startswith("/api/v1/integrations/erp") and settings.public_demo:
        raise HTTPException(403, "Private workspaces cannot access the public demo ERP simulator.")
    return actor
