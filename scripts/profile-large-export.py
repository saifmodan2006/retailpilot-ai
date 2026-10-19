"""Profile a full 4,320-row inventory export in the local 512 MB container.

Requires start-release-check.py and a seeded release-check tenant. Credentials
remain in memory; this never connects to the public deployment.
"""
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import jwt
from dotenv import dotenv_values
from sqlalchemy import create_engine, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
from app.models import Sale, User  # noqa: E402

env = dotenv_values(root / ".env")
container_env = json.loads(subprocess.check_output([
    "docker", "inspect", "retailpilot-release-check", "--format", "{{json .Config.Env}}"
]))
secret = dict(v.split("=", 1) for v in container_env)["JWT_SECRET"]
engine = create_engine(URL.create("postgresql+psycopg", username="retailpilot",
    password=env["POSTGRES_PASSWORD"], host="127.0.0.1", port=5433, database="retailpilot_release"))
with Session(engine) as db:
    user = db.scalar(select(User).where(User.org_id.in_(select(Sale.org_id).distinct())).limit(1))
    assert user, "Seed the local release-check database first"
    now = datetime.now(timezone.utc)
    token = jwt.encode({"sub": str(user.id), "org": user.org_id, "iss": "retailpilot",
        "aud": "retailpilot-api", "iat": now, "exp": now + timedelta(hours=1)}, secret, algorithm="HS256")
with httpx.Client(base_url="http://127.0.0.1:5180", timeout=240,
    headers={"Authorization": "Bearer " + token}) as client:
    result = client.post("/api/v1/reports", json={"kind": "SKU inventory"})
    result.raise_for_status()
    report = result.json()
    assert len(report["rows"]) == 4320
    evidence = {"inventory_rows": len(report["rows"]), "memory_limit_bytes": 512 * 1024**2}
    for fmt in ["xlsx", "pdf"]:
        start = time.monotonic()
        r = client.get(f"/api/v1/reports/{report['id']}/download?format={fmt}")
        r.raise_for_status()
        assert r.content.startswith(b"PK" if fmt == "xlsx" else b"%PDF")
        evidence[fmt] = {"bytes": len(r.content), "seconds": round(time.monotonic()-start, 2)}
    evidence["cgroup_peak_bytes"] = int(subprocess.check_output([
        "docker", "exec", "retailpilot-release-check", "cat", "/sys/fs/cgroup/memory.peak"
    ]))
    assert evidence["cgroup_peak_bytes"] < evidence["memory_limit_bytes"]
    (root / "docs/export-resource-verification.json").write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence))
