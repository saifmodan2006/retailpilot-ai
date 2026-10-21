"""Email PKCE state for Supabase's default Free mail templates.

Challenge generation and code exchange use the maintained Supabase Auth SDK.
An opaque HttpOnly cookie binds the link to its initiating browser. The provider
owns verification links; the application never implements OAuth credentials.
"""

import secrets
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from supabase_auth.helpers import generate_pkce_challenge, generate_pkce_verifier

from .account_auth import aware, decrypted, digest, encrypted
from .core import settings, utcnow
from .models import IdentityChallenge, OAuthChallenge

CHALLENGE_COOKIE = "rp-auth-challenge"


def reserve(db, request):
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy import text

        db.execute(text("SELECT pg_advisory_xact_lock(7319288)"))
    old = request.cookies.get(CHALLENGE_COOKIE)
    for model in (IdentityChallenge, OAuthChallenge):
        db.execute(delete(model).where(model.expires_at <= utcnow()))
        if old:
            db.execute(delete(model).where(model.digest == digest(old)))
    count = sum(
        db.scalar(select(func.count()).select_from(model))
        for model in (IdentityChallenge, OAuthChallenge)
    )
    if count >= 20:
        raise HTTPException(429, "Verification capacity reached. Please retry later.")


def begin(db, request, response, email, kind):
    reserve(db, request)
    if (
        db.scalar(
            select(func.count())
            .select_from(IdentityChallenge)
            .where(IdentityChallenge.email == email)
        )
        >= 2
    ):
        raise HTTPException(429, "Finish an existing email verification before requesting another.")
    verifier, secret = generate_pkce_verifier(), secrets.token_urlsafe(32)
    db.add(
        IdentityChallenge(
            digest=digest(secret),
            email=email,
            kind=kind,
            verifier=encrypted({"code_verifier": verifier}),
            expires_at=utcnow() + timedelta(minutes=30),
        )
    )
    response.set_cookie(
        CHALLENGE_COOKIE,
        secret,
        max_age=1800,
        httponly=True,
        secure=settings.account_cookie_secure,
        samesite="lax",
        path="/api/v1",
    )
    return generate_pkce_challenge(verifier)


def begin_google(db, request, response, verifier):
    reserve(db, request)
    if not verifier:
        raise HTTPException(503, "The identity provider could not prepare secure Google sign-in.")
    secret = secrets.token_urlsafe(32)
    db.add(
        OAuthChallenge(
            digest=digest(secret),
            verifier=encrypted({"code_verifier": verifier}),
            expires_at=utcnow() + timedelta(minutes=10),
        )
    )
    response.set_cookie(
        CHALLENGE_COOKIE,
        secret,
        max_age=600,
        httponly=True,
        secure=settings.account_cookie_secure,
        samesite="lax",
        path="/api/v1",
    )


def pending(db, request):
    row = db.scalar(
        select(IdentityChallenge)
        .where(IdentityChallenge.digest == digest(request.cookies.get(CHALLENGE_COOKIE, "")))
        .with_for_update()
    )
    if not row:
        row = db.scalar(
            select(OAuthChallenge)
            .where(OAuthChallenge.digest == digest(request.cookies.get(CHALLENGE_COOKIE, "")))
            .with_for_update()
        )
    if not row or aware(row.expires_at) <= utcnow():
        raise HTTPException(
            401,
            "This verification link has expired, was used, or was opened in a different browser. Request a fresh email on this browser.",
        )
    return row, decrypted(row.verifier)["code_verifier"]


def consume(db, request, response):
    secret = request.cookies.get(CHALLENGE_COOKIE)
    if secret:
        for model in (IdentityChallenge, OAuthChallenge):
            db.execute(delete(model).where(model.digest == digest(secret)))
    response.delete_cookie(
        CHALLENGE_COOKIE,
        path="/api/v1",
        secure=settings.account_cookie_secure,
        httponly=True,
        samesite="lax",
    )
