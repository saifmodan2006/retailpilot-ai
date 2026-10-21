from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select

from .analytics import Filters, inventory_metrics
from .core import SessionLocal
from .models import AuditEvent, Organization, Recommendation, Workflow
from .reports import create_report
from .seed import AS_OF

TRANSITIONS = {
    "Pending": {"Running", "Cancelled"},
    "Running": {"Completed", "Failed", "Awaiting Approval"},
    "Failed": {"Pending", "Cancelled"},
    "Awaiting Approval": {"Completed", "Rejected", "Cancelled"},
    "Completed": set(),
    "Rejected": set(),
    "Cancelled": set(),
}


def transition(row, target):
    if target not in TRANSITIONS.get(row.status, set()):
        raise HTTPException(409, f"Invalid transition: {row.status} → {target}")
    row.status = target


def audit(db, user, action, entity, detail=None):
    db.add(
        AuditEvent(
            org_id=user.org_id,
            actor=f"{user.name} ({user.role})",
            action=action,
            entity=str(entity),
            detail={"actor_user_id": user.id, **(detail or {})},
        )
    )


def recommendation_values(r):
    return {
        "quantity": r["reorder_quantity"],
        "cost": round(r["reorder_quantity"] * r["cost"], 2),
        "severity": "Critical" if (r["cover_days"] or 0) < 7 else "Review",
        "rationale": f"{r['daily_demand']:.2f} units/day × {r['lead_days']} lead days + {r['safety_stock']} safety units − {r['available']} available − {r['inbound']} confirmed inbound. Rounded to pack of {r['pack_size']}.",
        "evidence": {
            k: r[k]
            for k in [
                "daily_demand",
                "available",
                "inbound",
                "lead_days",
                "safety_stock",
                "reorder_point",
                "pack_size",
                "moq",
                "cover_days",
            ]
        },
    }


def recommendations(db, org, config):
    metrics = inventory_metrics(db, org, Filters(), config)
    existing = {
        (r.store_id, r.sku_id)
        for r in db.scalars(
            select(Recommendation).where(
                Recommendation.org_id == org,
                Recommendation.status.in_(["Suggested", "Awaiting Approval", "Approved"]),
            )
        )
    }
    count = 0
    for r in metrics:
        if r["reorder_quantity"] <= 0 or (r["store_id"], r["sku_id"]) in existing:
            continue
        db.add(
            Recommendation(
                org_id=org,
                store_id=r["store_id"],
                sku_id=r["sku_id"],
                **recommendation_values(r),
            )
        )
        count += 1
    db.flush()
    return count


def execute(workflow_id):
    with SessionLocal() as db:
        row = db.get(Workflow, workflow_id)
        if not row or row.status != "Pending":
            return
        try:
            transition(row, "Running")
            row.attempts += 1
            row.error = ""
            db.commit()
            org = db.get(Organization, row.org_id)
            if row.kind == "low-stock":
                row.result = {"recommendations_created": recommendations(db, org.id, org.settings)}
            elif row.kind in ["daily-report", "weekly-mis"]:
                f = Filters(
                    start=AS_OF if row.kind == "daily-report" else AS_OF - timedelta(days=6)
                )
                report = create_report(
                    db,
                    org.id,
                    "Daily sales MIS" if row.kind == "daily-report" else "Weekly store performance",
                    f,
                    org.settings,
                )
                row.result = {
                    "report_id": report.id,
                    "revenue": report.metrics["revenue"],
                }
                if row.kind == "weekly-mis":
                    previous = create_report(
                        db,
                        org.id,
                        "Weekly store performance",
                        Filters(
                            start=AS_OF - timedelta(days=13),
                            end=AS_OF - timedelta(days=7),
                        ),
                        org.settings,
                    )
                    row.result = {
                        **row.result,
                        "previous_report_id": previous.id,
                        "previous_revenue": previous.metrics["revenue"],
                        "change": report.metrics["revenue"] - previous.metrics["revenue"],
                    }
            else:
                raise ValueError("Unsupported workflow")
            transition(row, "Completed")
            db.add(
                AuditEvent(
                    org_id=row.org_id,
                    actor="Workflow engine",
                    action="workflow.completed",
                    entity=str(row.id),
                    detail=row.result,
                )
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            row = db.get(Workflow, workflow_id)
            row.status, row.error = "Failed", str(exc)[:500]
            db.commit()
