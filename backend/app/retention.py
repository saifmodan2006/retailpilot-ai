"""Bound pilot artifacts on access; no scheduler or paid worker is required.

History and business facts are retained. Raw previews expire after seven days,
report row payloads after thirty. No organization or sales record is deleted.
"""

from datetime import timedelta

from sqlalchemy import delete, select

from .core import utcnow
from .models import AuditEvent, ImportBatch, Report


def maintain_workspace(db, org):
    for batch in db.scalars(
        select(ImportBatch).where(
            ImportBatch.org_id == org.id, ImportBatch.created_at < utcnow() - timedelta(days=7)
        )
    ):
        if batch.payload:
            batch.payload = []
            if batch.status != "Imported":
                batch.status = "Expired"
    for report in db.scalars(
        select(Report).where(
            Report.org_id == org.id, Report.created_at < utcnow() - timedelta(days=30)
        )
    ):
        if report.rows:
            report.rows = []
    old_ids = list(
        db.scalars(
            select(AuditEvent.id)
            .where(AuditEvent.org_id == org.id)
            .order_by(AuditEvent.id.desc())
            .offset(1000)
        )
    )
    if old_ids:
        db.execute(delete(AuditEvent).where(AuditEvent.id.in_(old_ids)))
