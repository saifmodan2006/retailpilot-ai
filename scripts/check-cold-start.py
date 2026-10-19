"""Measure a genuine idle wake-up without keep-alive requests (16 minutes)."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

url = "https://retailpilot-ai-api.onrender.com/api/v1/health"
evidence = {"url": url, "started_at": datetime.now(timezone.utc).isoformat(), "idle_seconds": 960}
with httpx.Client(timeout=180) as client:
    start = time.monotonic()
    response = client.get(url)
    response.raise_for_status()
    evidence["warm_seconds"] = round(time.monotonic()-start, 3)
    print("Idle wake-up check started. No application requests for 16 minutes.", flush=True)
    for minute in range(16):
        time.sleep(60)
        print(f"Idle interval: {minute+1}/16 minutes; no keep-alive traffic sent.", flush=True)
    start = time.monotonic()
    response = client.get(url)
    response.raise_for_status()
    assert response.json()["status"] == "ok"
    evidence["wake_seconds"] = round(time.monotonic()-start, 3)
    evidence["status"] = response.status_code
    evidence["finished_at"] = datetime.now(timezone.utc).isoformat()
    evidence["limitation"] = "Elapsed idle window and request timing are measured; provider suspension state is separately observed in Render."
    output = Path(__file__).resolve().parents[1] / "docs/cold-start-verification.json"
    output.write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence), flush=True)
