"""Measure one real fictional seed on Render and end its disposable session."""
import json
import time
from pathlib import Path

import httpx

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "sample_data/manifest.json").read_text())
previous = json.loads((root / "docs/public-runtime-verification.json").read_text())
evidence = {"api": "https://retailpilot-ai-api.onrender.com", "seed": manifest["seed"]}
with httpx.Client(base_url=evidence["api"], timeout=180) as client:
    r = client.post("/api/v1/demo/session")
    r.raise_for_status()
    client.headers["Authorization"] = "Bearer " + r.json()["access_token"]
    try:
        start = time.monotonic()
        r = client.post("/api/v1/demo/seed")
        r.raise_for_status()
        evidence["seed_seconds"] = round(time.monotonic()-start, 3)
        for key, value in manifest.items():
            assert r.json()[key] == value, key
        evidence["counts_match_manifest"] = True
        r = client.get("/api/v1/analytics")
        r.raise_for_status()
        metrics = r.json()["metrics"]
        assert abs(metrics["revenue"] - (previous["revenue"]-55532.25)) < 0.01
        assert metrics["inventory_value"] == previous["report_metrics"]["inventory_value"]
        evidence["baseline_metrics_unchanged"] = True
    finally:
        r = client.post("/api/v1/demo/end")
        r.raise_for_status()
        assert client.get("/api/v1/me").status_code == 403
        evidence["disposable_session_ended"] = True
(root / "docs/seed-performance-verification.json").write_text(json.dumps(evidence, indent=2))
print(json.dumps(evidence))
