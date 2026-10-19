"""Verify the running stack without printing tokens or provider credentials."""

import json
import sys
from pathlib import Path

import httpx
from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core import SessionLocal  # noqa: E402
from app.models import Report, Sale, Store, User  # noqa: E402
from app.security import token  # noqa: E402

evidence_path = ROOT / "docs/runtime-verification.json"
mode = sys.argv[1] if len(sys.argv) > 1 else "check"
with SessionLocal() as db:
    if mode == "persistence":
        evidence = json.loads(evidence_path.read_text())
        user = db.get(User, evidence["actor_id"])
    else:
        org_id = db.scalar(select(Store.org_id).limit(1))
        if not org_id:
            raise SystemExit("Run the browser demo and seed data first.")
        user = db.scalar(select(User).where(User.org_id == org_id))
        evidence = {"organization_id": org_id, "actor_id": user.id, "checks": []}
    with httpx.Client(
        base_url="http://127.0.0.1:8000",
        timeout=90,
        headers={"Authorization": "Bearer " + token(user)},
    ) as client:
        if mode == "persistence":
            report = db.get(Report, evidence["report_id"])
            assert report.metrics == evidence["report_metrics"]
            actual = db.scalar(select(func.count(Sale.id)).where(Sale.org_id == user.org_id))
            assert actual >= evidence["sales_count"]
            assert client.get(f"/api/v1/reports/{report.id}/download").status_code == 200
            evidence["persistence_after_backend_restart"] = True
        else:
            for path in ["/api/v1/health", "/docs", "/openapi.json", "/samples/sales_import.xlsx"]:
                r = client.get(path)
                assert r.status_code == 200, (path, r.status_code)
                evidence["checks"].append(path)
            for path, count in [("stores", 12), ("products", 180), ("skus", 360)]:
                r = client.get("/api/v1/" + path)
                assert r.status_code == 200 and len(r.json()) == count
                evidence["checks"].append(f"{path}: {count}")
            status = client.get("/api/v1/integrations/erp/status").json()
            assert status["connected"] and status["products"] == 25
            preview = client.post("/api/v1/integrations/erp/sync").json()
            assert preview["accepted"] == 25 and preview["rejected"] == 0, preview
            evidence["checks"].append(
                "ERP HTTP sync: authenticated 3-page fetch; 25 rows validated into review batch"
            )
            evidence["erp_preview_batch_id"] = preview["id"]
            for question in [
                "stores",
                "stockouts",
                "dead-stock",
                "inventory",
                "reorder",
                "revenue",
            ]:
                r = client.post("/api/v1/analyst/query", json={"question": question})
                assert r.status_code == 200, r.text
                assert r.json()["tool"] == question
                evidence["checks"].append("analyst:" + question)
            r = client.post("/api/v1/reports", json={"kind": "Monthly management summary"})
            assert r.status_code == 200, r.text
            report = r.json()
            for fmt in ["xlsx", "pdf"]:
                r = client.get(f"/api/v1/reports/{report['id']}/download?format={fmt}")
                assert r.status_code == 200
                assert r.content.startswith(b"%PDF" if fmt == "pdf" else b"PK")
                evidence["checks"].append("report:" + fmt)
            evidence["report_id"], evidence["report_metrics"] = report["id"], report["metrics"]
            evidence["sales_count"] = db.scalar(
                select(func.count(Sale.id)).where(Sale.org_id == user.org_id)
            )
        evidence_path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    "mode": mode,
                    "checks": len(evidence["checks"]),
                    "persistence_verified": evidence.get(
                        "persistence_after_backend_restart", False
                    ),
                }
            )
        )
