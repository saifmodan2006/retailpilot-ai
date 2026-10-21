"""Public portfolio boundaries: no private tenant, arbitrary file or provider access."""

import hashlib
from datetime import timedelta, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import delete, func, select, text, or_

from .core import Base, settings, utcnow
from .models import Organization, Workflow


def demo_only(db, user):
    org = db.get(Organization, user.org_id)
    if not org or not org.is_demo:
        raise HTTPException(403, "This action is restricted to a fictional demo organization")
    return org


def expiry(org):
    created = org.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return created + timedelta(hours=settings.demo_ttl_hours)


def admit_session(db):
    if not settings.public_demo:
        return
    # Serialize quota checks across PostgreSQL request transactions.
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(7319284)"))
    cutoff = utcnow() - timedelta(hours=settings.demo_ttl_hours)
    expired = list(
        db.scalars(
            select(Organization.id).where(
                Organization.is_demo.is_(True),
                or_(
                    Organization.created_at < cutoff,
                    Organization.settings["_demo_ended"].as_boolean().is_(True),
                ),
            )
        )
    )
    for org_id in expired:
        running = db.scalar(
            select(Workflow.id)
            .where(Workflow.org_id == org_id, Workflow.status == "Running")
            .limit(1)
        )
        if running:
            continue
        for table in reversed(Base.metadata.sorted_tables):
            if "org_id" in table.c:
                db.execute(delete(table).where(table.c.org_id == org_id))
        db.execute(
            delete(Organization).where(Organization.id == org_id, Organization.is_demo.is_(True))
        )
    count = db.scalar(
        select(func.count()).select_from(Organization).where(Organization.is_demo.is_(True))
    )
    if count >= settings.demo_max_tenants:
        raise HTTPException(
            429, "The demo is at capacity. Please try again after an existing session expires."
        )


def quota(db, user, model, maximum):
    from .models import Membership

    persistent = db.scalar(select(Membership.id).where(Membership.actor_id == user.id))
    if not settings.public_demo and not persistent:
        return
    db.scalar(select(Organization).where(Organization.id == user.org_id).with_for_update())
    count = db.scalar(select(func.count()).select_from(model).where(model.org_id == user.org_id))
    if count >= maximum:
        raise HTTPException(
            429,
            f"Workspace limit reached ({maximum} {model.__tablename__}). Review retention and capacity with the operator.",
        )


def permitted_upload(content, private=False):
    if private and settings.real_uploads_enabled:
        return
    if not settings.public_demo and not private:
        return
    samples = Path(__file__).resolve().parents[2] / "sample_data"
    accepted = {
        hashlib.sha256(p.read_bytes()).digest()
        for p in samples.iterdir()
        if p.suffix in [".csv", ".xlsx"]
    }
    if hashlib.sha256(content).digest() not in accepted:
        raise HTTPException(
            403,
            "Public demo accepts only the supplied fictional XLSX/CSV samples. Use a private local deployment for your own data.",
        )
