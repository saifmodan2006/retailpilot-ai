"""Non-destructive public account boundary checks. Never signs up a real user."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

origin = "https://retailpilot-ai.pages.dev"
api = "https://retailpilot-ai-api.onrender.com"
evidence = {"checked_at": datetime.now(timezone.utc).isoformat(), "frontend": origin, "api": api, "checks": []}
pilot = "--pilot" in sys.argv
evidence["registration_mode"] = "Approved restricted pilot" if pilot else "Closed"


def check(name, condition):
    assert condition, name
    evidence["checks"].append(name)


with httpx.Client(timeout=120) as client:
    check("Direct API HTTPS health", client.get(api + "/api/v1/health").status_code == 200)
    r = client.get(origin + "/api/v1/auth/config")
    config = r.json()
    check("Pages Functions reaches actual account API", r.status_code == 200 and config["configured"])
    check("Restricted pilot UI enabled" if pilot else "Registration closed", config["registration"] == pilot)
    check("Arbitrary uploads closed", not config["real_uploads"])
    check("Google disabled", not config["google"])
    check("Identity responses never cached", r.headers.get("cache-control") == "no-store")
    for path in ("account/profile", "organizations", "organizations/current/team", "me"):
        check("Anonymous rejected: " + path, client.get(origin + "/api/v1/" + path).status_code == 401)
    headers = {"Origin": origin, "X-RP-CSRF": "1"}
    r = client.post(origin + "/api/v1/auth/signup", headers=headers,
                    json={"email": "blocked@example.test", "password": "fictional-unusable-passphrase"})
    check("Non-admitted signup rejected", r.status_code == 403)
    r = client.post(origin + "/api/v1/auth/login", headers={"Origin": "https://attacker.example", "X-RP-CSRF": "1"},
                    json={"email": "blocked@example.test", "password": "fictional-unusable-passphrase"})
    check("Forged Origin rejected", r.status_code == 403)
    for path in ("/", "/auth/login", "/auth/signup", "/auth/callback", "/onboarding/", "/app/overview"):
        r = client.get(origin + path)
        check("SPA refresh: " + path, r.status_code == 200 and "<html" in r.text.lower())
    r = client.get(origin + "/onboarding", follow_redirects=True)
    check("Onboarding canonical redirect preserves route", r.status_code == 200 and r.url.path == "/onboarding/")
    for path in ("/docs", "/openapi.json"):
        check("Public API docs restricted: " + path, client.get(api + path).status_code == 404)
    r = client.options(api + "/api/v1/me", headers={"Origin": "https://attacker.example", "Access-Control-Request-Method": "GET"})
    check("CORS rejects unrelated origin", r.status_code == 400 and "access-control-allow-origin" not in r.headers)

Path("docs/saas-public-http-verification.json").write_text(json.dumps(evidence, indent=2) + "\n")
print(json.dumps(evidence, indent=2))
