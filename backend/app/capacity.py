"""Shared storage admission checks; limits never enable paid capacity."""

from fastapi import HTTPException
from sqlalchemy import String, cast, func, select, text

from .core import settings
from .models import ImportBatch, Inventory, Report, Sale


def storage_budget(db, sales=0, inventory=0):
    if not (settings.public_demo or settings.accounts_enabled):
        return
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(7319291)"))
        if db.scalar(text("SELECT pg_database_size(current_database())")) >= 450_000_000:
            raise HTTPException(429, "Shared storage capacity reached. No new data was saved.")
    for model, addition, maximum in [(Sale, sales, 400000), (Inventory, inventory, 40000)]:
        if db.scalar(select(func.count()).select_from(model)) + addition > maximum:
            raise HTTPException(429, "Shared row capacity reached. No data was imported.")
    size = func.octet_length if db.bind.dialect.name == "postgresql" else func.length
    payload = sum(
        db.scalar(select(func.coalesce(func.sum(size(cast(column, String))), 0))) or 0
        for column in (ImportBatch.payload, Report.rows)
    )
    if payload > 40_000_000:
        raise HTTPException(429, "Shared preview/export capacity reached. No new data was saved.")
