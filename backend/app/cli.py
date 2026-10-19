"""Operator entry points; run from backend with python -m app.cli."""

import argparse
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from .core import SessionLocal
from .models import Organization, Workflow
from .workflows import execute

parser = argparse.ArgumentParser()
parser.add_argument("command", choices=["schedule"])
parser.add_argument(
    "--kind",
    choices=["daily-report", "weekly-mis", "low-stock"],
    default="daily-report",
)
args = parser.parse_args()
day = datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()
with SessionLocal() as db:
    for org in db.scalars(select(Organization)):
        key = f"schedule:{args.kind}:{day}"
        row = db.scalar(select(Workflow).where(Workflow.org_id == org.id, Workflow.key == key))
        if not row:
            row = Workflow(org_id=org.id, kind=args.kind, key=key)
            db.add(row)
            db.commit()
        execute(row.id)
        print(f"{org.id} {args.kind} {day}")
