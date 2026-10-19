import time
from collections import defaultdict, deque
from datetime import timedelta
from threading import Lock

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .core import get_db, settings, utcnow
from .models import Organization, User
from .demo import expiry

bearer = HTTPBearer()
attempts = defaultdict(deque)
limit_lock = Lock()


def rate_limit(request: Request, bucket="api", limit=180):
    key = (request.client.host if request.client else "local", bucket)
    now = time.monotonic()
    with limit_lock:
        if len(attempts) > 4096:
            for old in [k for k, q in attempts.items() if not q or q[-1] < now - 60]:
                attempts.pop(old, None)
            if len(attempts) > 4096 and key not in attempts:
                raise HTTPException(
                    429, "Request capacity reached. Retry shortly.", headers={"Retry-After": "60"}
                )
        queue = attempts[key]
        while queue and queue[0] < now - 60:
            queue.popleft()
        if len(queue) >= limit:
            raise HTTPException(
                429, "Rate limit exceeded. Retry in one minute.", headers={"Retry-After": "60"}
            )
        queue.append(now)


def token(user):
    return jwt.encode(
        {
            "sub": str(user.id),
            "org": user.org_id,
            "iss": "retailpilot",
            "aud": "retailpilot-api",
            "iat": utcnow(),
            "exp": utcnow()
            + timedelta(hours=settings.demo_ttl_hours if settings.public_demo else 8),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )


def current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db, scope="function"),
):
    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=["HS256"],
            issuer="retailpilot",
            audience="retailpilot-api",
            options={"require": ["sub", "org", "exp", "iat", "iss", "aud"]},
        )
        user = db.get(User, int(claims["sub"]))
        if not user or user.org_id != claims["org"]:
            raise ValueError("Unknown user")
        rate_limit(request, bucket=f"user:{user.id}")
        if settings.public_demo:
            org = db.get(Organization, user.org_id)
            if not org or not org.is_demo or expiry(org) <= utcnow():
                raise HTTPException(
                    403, "Public demo session expired or organization is not a demo tenant"
                )
        return user
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        rate_limit(request, bucket="invalid-auth", limit=60)
        raise HTTPException(401, "Session expired. Start a new demo session.") from exc


def manager(user=Depends(current_user)):
    if user.role != "manager":
        raise HTTPException(403, "A manager role is required")
    return user
