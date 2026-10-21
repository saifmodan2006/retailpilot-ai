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
from .models import IdentityChallenge

CHALLENGE_COOKIE = "rp-auth-challenge"


def begin(db, request, response, email, kind):
    db.execute(delete(IdentityChallenge).where(IdentityChallenge.expires_at <= utcnow()))
    old = request.cookies.get(CHALLENGE_COOKIE)
    if old:
        db.execute(delete(IdentityChallenge).where(IdentityChallenge.digest == digest(old)))
    if db.scalar(select(func.count()).select_from(IdentityChallenge)) >= 20:
        raise HTTPException(429, "Verification capacity reached. Please retry later.")
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


def pending(db, request):
    row = db.scalar(
        select(IdentityChallenge)
        .where(IdentityChallenge.digest == digest(request.cookies.get(CHALLENGE_COOKIE, "")))
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
        db.execute(delete(IdentityChallenge).where(IdentityChallenge.digest == digest(secret)))
    response.delete_cookie(
        CHALLENGE_COOKIE,
        path="/api/v1",
        secure=settings.account_cookie_secure,
        httponly=True,
        samesite="lax",
    )
