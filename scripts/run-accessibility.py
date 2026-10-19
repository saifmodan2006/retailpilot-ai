"""Reuse a local fictional tenant for read-only accessibility checks, without token files."""

import os
import subprocess
import sys
from pathlib import Path
from sqlalchemy import select

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
from app.core import SessionLocal  # noqa: E402
from app.models import Organization, Store, User  # noqa: E402
from app.security import token  # noqa: E402

with SessionLocal() as db:
    user = db.scalar(
        select(User)
        .join(Organization, User.org_id == Organization.id)
        .where(Organization.is_demo.is_(True), User.org_id.in_(select(Store.org_id)))
        .limit(1)
    )
    assert user, "Load a local fictional demo first"
    local_base = os.environ.get("LOCAL_AUDIT_BASE_URL", "http://127.0.0.1:5173")
    env = dict(
        os.environ,
        LOCAL_AUDIT_TOKEN=token(user),
        LOCAL_AUDIT_BASE_URL=local_base,
        E2E_BASE_URL=local_base,
    )
    command = (
        ["node", "scripts/visual-audit.mjs", "after"]
        if "--visual" in sys.argv
        else ["node", "scripts/accessibility-audit.mjs"]
    )
    raise SystemExit(subprocess.call(command, cwd=root / "frontend", env=env))
