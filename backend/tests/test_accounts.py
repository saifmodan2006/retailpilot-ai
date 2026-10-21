"""Managed provider is mocked at its HTTP boundary, never replaced in production.

No test authentication endpoint, shared test password or bypass ships in app code.
"""

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import select

from app.account_auth import provider
from app.core import SessionLocal, settings, utcnow
from app.models import Account, AccountSession

ORIGIN = {"Origin": "http://testserver", "X-RP-CSRF": "1"}


@pytest.fixture
def identity(client, monkeypatch):
    for key, value in {
        "accounts_enabled": True,
        "registration_enabled": True,
        "registration_allowlist": "owner@example.test,member@example.test,other@example.test,links@example.test",
        "session_encryption_key": Fernet.generate_key().decode(),
        "account_cookie_secure": False,
        "app_origin": "http://testserver",
    }.items():
        monkeypatch.setattr(settings, key, value)
    from identity_stub import FakeIdentity

    fake = FakeIdentity()
    monkeypatch.setattr(provider, "call", fake.call)
    monkeypatch.setattr(provider, "exchange", fake.exchange)
    return fake.users


def register(client, email="owner@example.test"):
    assert (
        client.post(
            "/api/v1/auth/signup",
            headers=ORIGIN,
            json={"email": email, "password": "fictional-test-passphrase"},
        ).status_code
        == 200
    )
    result = client.post(
        "/api/v1/auth/verify",
        headers=ORIGIN,
        json={"email": email, "token": "123456", "kind": "signup"},
    )
    assert result.status_code == 200, result.text
    return result.json()["profile"]


def test_email_change_uses_allowlisted_callback(client, identity, monkeypatch):
    register(client)
    original = provider.call
    observed = []

    def capture(method, path, body=None, access=None):
        if method == "PUT":
            observed.append(path)
        return original(method, path, body, access)

    monkeypatch.setattr(provider, "call", capture)
    result = client.post(
        "/api/v1/account/email", headers=ORIGIN, json={"email": "member@example.test"}
    )
    assert result.status_code == 200
    assert observed == ["user?redirect_to=http%3A%2F%2Ftestserver%2Fauth%2Fcallback"]


def test_verified_registration_http_only_and_profile(client, identity):
    result = register(client)
    cookie = client.cookies.get("rp-account")
    assert cookie and "opaque" not in cookie
    response = client.get("/api/v1/account/profile")
    assert response.json()["id"] == result["id"]
    edited = client.patch(
        "/api/v1/account/profile",
        headers=ORIGIN,
        json={"name": "Fictional Owner", "job_title": "Retail analyst", "timezone": "Asia/Kolkata"},
    )
    assert edited.status_code == 200
    assert "provider_id" not in edited.json()
    with SessionLocal() as db:
        row = db.scalar(select(AccountSession))
        assert row.digest != cookie and "opaque" not in row.provider_tokens
    client.post("/api/v1/auth/logout", headers=ORIGIN)
    assert client.get("/api/v1/account/profile").status_code == 401
    login = client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": "owner@example.test", "password": "fictional-test-passphrase"},
    )
    assert login.status_code == 200
    assert (
        "HttpOnly" in login.headers["set-cookie"] and "SameSite=lax" in login.headers["set-cookie"]
    )
    assert client.get("/api/v1/account/profile").json()["name"] == "Fictional Owner"


def test_verification_replay_invalid_and_unverified_login(client, identity):
    client.post(
        "/api/v1/auth/signup",
        headers=ORIGIN,
        json={"email": "owner@example.test", "password": "fictional-test-passphrase"},
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            headers=ORIGIN,
            json={"email": "owner@example.test", "password": "fictional-test-passphrase"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/auth/verify",
            headers=ORIGIN,
            json={"email": "owner@example.test", "token": "654321"},
        ).status_code
        == 401
    )
    valid = {"email": "owner@example.test", "token": "123456"}
    assert client.post("/api/v1/auth/verify", headers=ORIGIN, json=valid).status_code == 200
    assert client.post("/api/v1/auth/verify", headers=ORIGIN, json=valid).status_code == 401


def test_csrf_registration_gate_and_profile_isolation(client, identity, monkeypatch):
    register(client)
    assert client.patch("/api/v1/account/profile", json={"name": "Forged"}).status_code == 403
    assert (
        client.post(
            "/api/v1/auth/logout", headers={**ORIGIN, "Origin": "https://attacker.example"}
        ).status_code
        == 403
    )
    other = register(client, "other@example.test")
    assert client.get("/api/v1/account/profile").json()["id"] == other["id"]
    assert client.get("/api/v1/account/profile?account_id=owner").json()["id"] == other["id"]
    monkeypatch.setattr(settings, "registration_enabled", False)
    assert (
        client.post(
            "/api/v1/auth/signup",
            headers=ORIGIN,
            json={"email": "member@example.test", "password": "fictional-test-passphrase"},
        ).status_code
        == 403
    )


def test_recovery_replay_and_revocation(client, identity):
    register(client)
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            headers=ORIGIN,
            json={"password": "a-new-fictional-password"},
        ).status_code
        == 403
    )
    request = {"email": "owner@example.test", "token": "123456", "kind": "recovery"}
    assert client.post("/api/v1/auth/verify", headers=ORIGIN, json=request).status_code == 200
    assert (
        client.patch(
            "/api/v1/account/profile", headers=ORIGIN, json={"name": "Recovery cannot edit"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            headers=ORIGIN,
            json={"password": "a-new-fictional-password"},
        ).status_code
        == 200
    )
    assert client.get("/api/v1/account/profile").status_code == 401
    assert client.post("/api/v1/auth/verify", headers=ORIGIN, json=request).status_code == 401
    assert (
        client.post(
            "/api/v1/auth/login",
            headers=ORIGIN,
            json={"email": "owner@example.test", "password": "a-new-fictional-password"},
        ).status_code
        == 200
    )


def test_expired_session_and_provider_down_logout(client, identity, monkeypatch):
    register(client)
    cookie = client.cookies.get("rp-account")

    def unavailable(*args, **kwargs):
        raise HTTPException(503, "Provider unavailable")

    monkeypatch.setattr(provider, "call", unavailable)
    assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 200
    client.cookies.set("rp-account", cookie)
    assert client.get("/api/v1/account/profile").status_code == 401


def test_account_defaults_fail_closed(client):
    assert client.get("/api/v1/auth/config").json()["configured"] is False
    response = client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": "owner@example.test", "password": "fictional-test-passphrase"},
    )
    assert response.status_code in (403, 503)
    demo = client.post("/api/v1/demo/session").json()
    assert (
        client.get(
            "/api/v1/account/profile", headers={"Authorization": "Bearer " + demo["access_token"]}
        ).status_code
        == 503
    )


def new_org(client, name="Fictional private retail"):
    result = client.post("/api/v1/organizations", headers=ORIGIN, json={"name": name})
    assert result.status_code == 200, result.text
    return result.json()


def test_onboarding_resumes_and_completion_is_idempotent(client, identity):
    register(client)
    assert client.post("/api/v1/onboarding/complete", headers=ORIGIN).status_code == 422
    assert (
        client.patch(
            "/api/v1/account/profile", headers=ORIGIN, json={"name": "Private owner"}
        ).status_code
        == 200
    )
    draft = {
        "step": 2,
        "business": {"name": "Fictional onboarding retail"},
        "stores": [{"code": "TEST", "name": "Fictional store", "city": "Test city"}],
        "start": "empty",
    }
    assert client.patch("/api/v1/onboarding", headers=ORIGIN, json=draft).status_code == 200
    assert client.get("/api/v1/onboarding").json()["step"] == 2
    assert client.post("/api/v1/onboarding/complete", headers=ORIGIN).status_code == 422
    draft["step"] = 3
    client.patch("/api/v1/onboarding", headers=ORIGIN, json=draft)
    first = client.post("/api/v1/onboarding/complete", headers=ORIGIN)
    second = client.post("/api/v1/onboarding/complete", headers=ORIGIN)
    assert first.status_code == second.status_code == 200
    assert first.json()["organization_id"] == second.json()["organization_id"]
    assert len(client.get("/api/v1/organizations").json()["organizations"]) == 1
    org = client.get("/api/v1/organizations/current").json()
    assert org["role"] == "owner" and org["owners"]
    assert client.get("/api/v1/stores").json()[0]["code"] == "TEST"


def test_switching_owner_limits_and_nonmember_rejection(client, identity):
    register(client)
    one, two = new_org(client), new_org(client, "Second fictional retail")
    assert (
        client.post(
            "/api/v1/organizations", headers=ORIGIN, json={"name": "Third retail"}
        ).status_code
        == 429
    )
    assert (
        client.post(
            "/api/v1/organizations/select", headers=ORIGIN, json={"organization_id": one["id"]}
        ).status_code
        == 200
    )
    assert client.get("/api/v1/me").json()["organization"] == one["name"]
    assert client.post("/api/v1/organizations/current/leave", headers=ORIGIN).status_code == 409
    register(client, "other@example.test")
    assert (
        client.post(
            "/api/v1/organizations/select", headers=ORIGIN, json={"organization_id": two["id"]}
        ).status_code
        == 403
    )
    assert client.get("/api/v1/organizations").json()["organizations"] == []
    assert client.get("/api/v1/analytics").status_code == 403


def test_org_edit_stores_closure_and_deletion_request(client, identity):
    register(client)
    org = new_org(client)
    assert (
        client.patch(
            "/api/v1/organizations/current",
            headers=ORIGIN,
            json={
                "name": "Renamed fictional business",
                "currency": "USD",
                "timezone": "America/New_York",
            },
        ).status_code
        == 200
    )
    assert (
        client.patch(
            "/api/v1/organizations/current",
            headers=ORIGIN,
            json={"name": "Wrong timezone", "timezone": "invented/zone"},
        ).status_code
        == 422
    )
    store = client.post(
        "/api/v1/organizations/current/stores",
        headers=ORIGIN,
        json={"code": "F01", "name": "Fictional store", "city": "Fictional city"},
    )
    assert store.status_code == 200
    assert (
        client.patch(
            f"/api/v1/organizations/current/stores/{store.json()['id']}",
            headers=ORIGIN,
            json={"code": "F01", "name": "Edited fictional store"},
        ).status_code
        == 200
    )
    deletion = {"email": "owner@example.test", "confirmation": "REQUEST DELETION"}
    assert (
        client.post("/api/v1/account/deletion-request", headers=ORIGIN, json=deletion).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/organizations/current/close", headers=ORIGIN, json={"confirmation": "wrong"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/organizations/current/close",
            headers=ORIGIN,
            json={"confirmation": "Renamed fictional business"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/organizations/select", headers=ORIGIN, json={"organization_id": org["id"]}
        ).status_code
        == 403
    )
    assert (
        client.post("/api/v1/account/deletion-request", headers=ORIGIN, json=deletion).status_code
        == 200
    )
    assert client.get("/api/v1/account/profile").status_code == 401
    from app.models import Organization

    with SessionLocal() as db:
        assert db.get(Organization, org["id"]) is not None
        assert db.scalar(select(Account)).deletion_requested_at is not None


def invite_member(client, role="viewer", email="member@example.test"):
    result = client.post(
        "/api/v1/organizations/current/invitations",
        headers=ORIGIN,
        json={"email": email, "role": role},
    )
    assert result.status_code == 200, result.text
    assert result.json()["delivery"] == "not_delivered"
    return result.json(), result.json()["accept_url"].split("token=")[1]


def login_owner(client):
    result = client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": "owner@example.test", "password": "fictional-test-passphrase"},
    )
    assert result.status_code == 200, result.text


def test_invitation_email_binding_expiration_replay_and_revocation(client, identity):
    from datetime import timedelta
    from app.models import Invitation

    register(client)
    org = new_org(client)
    invitation, token = invite_member(client)
    register(client, "other@example.test")
    assert (
        client.post(
            "/api/v1/invitations/respond",
            headers=ORIGIN,
            json={"token": token, "decision": "accept"},
        ).status_code
        == 404
    )
    register(client, "member@example.test")
    accepted = client.post(
        "/api/v1/invitations/respond", headers=ORIGIN, json={"token": token, "decision": "accept"}
    )
    assert accepted.status_code == 200
    assert client.get("/api/v1/me").json()["user"]["role"] == "viewer"
    assert (
        client.post(
            "/api/v1/invitations/respond",
            headers=ORIGIN,
            json={"token": token, "decision": "accept"},
        ).status_code
        == 409
    )
    login_owner(client)
    expiring, expired_token = invite_member(client, email="other@example.test")
    with SessionLocal() as db:
        db.get(Invitation, expiring["id"]).expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert (
        next(
            i
            for i in client.get("/api/v1/organizations/current/team").json()["invitations"]
            if i["id"] == expiring["id"]
        )["status"]
        == "expired"
    )
    expiring, revoked_token = invite_member(client, email="other@example.test")
    assert (
        client.post(
            f"/api/v1/organizations/current/invitations/{expiring['id']}/revoke", headers=ORIGIN
        ).status_code
        == 200
    )
    assert org["id"]
    with SessionLocal() as db:
        assert all(
            row.token_digest not in (token, expired_token, revoked_token)
            for row in db.scalars(select(Invitation))
        )


def test_roles_final_owner_and_immediate_membership_revocation(client, identity):
    from app.models import Membership

    register(client)
    org = new_org(client)
    _, token = invite_member(client, "analyst")
    owner_cookie = client.cookies.get("rp-account")
    client.cookies.clear()  # Independent browser: signing into a different account rotates the old browser session.
    register(client, "member@example.test")
    assert (
        client.post(
            "/api/v1/invitations/respond",
            headers=ORIGIN,
            json={"token": token, "decision": "accept"},
        ).status_code
        == 200
    )
    member_cookie = client.cookies.get("rp-account")
    assert (
        client.post(
            "/api/v1/approvals/1/decision",
            headers=ORIGIN,
            json={"decision": "approve", "reason": "Forbidden attempt"},
        ).status_code
        == 403
    )
    assert client.get("/api/v1/organizations/current/team").status_code == 403
    with SessionLocal() as db:
        owner = db.scalar(
            select(Membership).where(Membership.org_id == org["id"], Membership.role == "owner")
        )
        member = db.scalar(
            select(Membership).where(Membership.org_id == org["id"], Membership.role == "analyst")
        )
        owner_id, member_id = owner.id, member.id
    client.cookies.clear()
    client.cookies.set("rp-account", owner_cookie)
    assert (
        client.patch(
            f"/api/v1/organizations/current/team/{owner_id}",
            headers=ORIGIN,
            json={"role": "viewer"},
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"/api/v1/organizations/current/team/{member_id}",
            headers=ORIGIN,
            json={"role": "admin"},
        ).status_code
        == 200
    )
    client.cookies.clear()
    client.cookies.set("rp-account", member_cookie)
    assert (
        client.post(
            "/api/v1/organizations/current/invitations",
            headers=ORIGIN,
            json={"email": "other@example.test", "role": "admin"},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/v1/organizations/current/team/{owner_id}",
            headers=ORIGIN,
            json={"role": "viewer"},
        ).status_code
        == 403
    )
    client.cookies.clear()
    client.cookies.set("rp-account", owner_cookie)
    assert (
        client.post(
            f"/api/v1/organizations/current/team/{member_id}/remove", headers=ORIGIN
        ).status_code
        == 200
    )
    client.cookies.clear()
    client.cookies.set("rp-account", member_cookie)
    assert client.get("/api/v1/analytics").status_code == 403
    assert (
        client.post(
            "/api/v1/organizations/select", headers=ORIGIN, json={"organization_id": org["id"]}
        ).status_code
        == 403
    )


def bind_fixture_account(client, fixture_data, role):
    from app.models import Membership, User

    account = register(client)
    with SessionLocal() as db:
        user = db.scalar(
            select(User).where(User.org_id == fixture_data["org"], User.role == "analyst")
        )
        user.role = role
        db.add(
            Membership(org_id=user.org_id, account_id=account["id"], actor_id=user.id, role=role)
        )
        db.scalar(select(AccountSession)).org_id = user.org_id
        db.commit()


def test_viewer_cannot_write_and_demo_token_cannot_impersonate_member(
    client, fixture_data, identity
):
    bind_fixture_account(client, fixture_data, "viewer")
    for path, payload in [
        ("/reports", {"kind": "Daily sales MIS"}),
        ("/workflows", {"kind": "low-stock", "key": "viewer-attempt"}),
        ("/analyst/query", {"question": "What is our inventory value?"}),
        ("/demo/role", {}),
        ("/demo/seed", {}),
        ("/recommendations/1/submit", {}),
    ]:
        assert client.post("/api/v1" + path, headers=ORIGIN, json=payload).status_code == 403, path
    assert (
        client.post(
            "/api/v1/imports/preview",
            headers=ORIGIN,
            files={"file": ("blocked.csv", b"date,sku\n")},
        ).status_code
        == 403
    )
    assert client.get("/api/v1/analytics").status_code == 200
    assert client.get("/api/v1/me", headers=fixture_data["analyst"]).status_code == 401
    from app.models import ForecastResult

    with SessionLocal() as db:
        assert list(db.scalars(select(ForecastResult))) == []


def test_analyst_import_permission_and_sample_only_private_upload(client, fixture_data, identity):
    from pathlib import Path
    from app.models import Organization

    bind_fixture_account(client, fixture_data, "analyst")
    sample = Path(__file__).resolve().parents[2] / "sample_data" / "sales_import.xlsx"

    def upload():
        return client.post(
            "/api/v1/imports/preview",
            headers=ORIGIN,
            files={"file": (sample.name, sample.read_bytes())},
        )

    assert upload().status_code == 403
    with SessionLocal() as db:
        org = db.get(Organization, fixture_data["org"])
        org.settings = {**org.settings, "analyst_imports_enabled": True}
        db.commit()
    assert upload().status_code == 200
    assert (
        client.post(
            "/api/v1/imports/preview",
            headers=ORIGIN,
            files={
                "file": (
                    "private.csv",
                    b"transaction_id,date,store,sku,quantity,revenue,cogs\nX,2026-10-18,ST01,RP-001-1,1,100,40\n",
                )
            },
        ).status_code
        == 403
    )
    assert client.post("/api/v1/demo/role", headers=ORIGIN).status_code == 403
    assert (
        client.post(
            "/api/v1/workflows",
            headers=ORIGIN,
            json={"kind": "low-stock", "key": "analyst-inventory"},
        ).status_code
        == 403
    )


def test_cross_org_reports_analyst_and_store_isolation(client, fixture_data, identity):
    bind_fixture_account(client, fixture_data, "owner")
    generated = client.post("/api/v1/reports", headers=ORIGIN, json={"kind": "Daily sales MIS"})
    assert generated.status_code == 200
    ident = generated.json()["id"]
    assert client.get(f"/api/v1/reports/{ident}/download").status_code == 200
    new_org(client, "Other private workspace")
    assert client.get(f"/api/v1/reports/{ident}/download").status_code == 404
    assert (
        client.patch(
            f"/api/v1/organizations/current/stores/{fixture_data['store']}",
            headers=ORIGIN,
            json={"code": "X", "name": "Forbidden"},
        ).status_code
        == 404
    )
    analytics = client.get("/api/v1/analytics?organization_id=" + fixture_data["org"])
    assert analytics.json()["metrics"]["revenue"] == 0
    answer = client.post(
        "/api/v1/analyst/query",
        headers=ORIGIN,
        json={"question": "What is our current inventory value?"},
    )
    assert answer.status_code == 200 and "267" not in str(answer.json())
    assert client.get("/api/v1/catalog").json()["stores"] == []


def test_retention_expires_artifacts_preserves_business_facts(client, fixture_data, identity):
    from datetime import timedelta
    from app.models import ImportBatch, Report, Sale

    bind_fixture_account(client, fixture_data, "owner")
    with SessionLocal() as db:
        batch = ImportBatch(
            org_id=fixture_data["org"],
            fingerprint="expired-fixture",
            filename="old-fictional.csv",
            kind="sales",
            payload=[{"old": "fictional"}],
            created_at=utcnow() - timedelta(days=8),
        )
        report = Report(
            org_id=fixture_data["org"],
            kind="Daily sales MIS",
            filters={},
            rows=[{"old": "fictional"}],
            metrics={},
            created_at=utcnow() - timedelta(days=31),
        )
        db.add_all([batch, report])
        db.commit()
        batch_id, report_id = batch.id, report.id
        sales_before = list(db.scalars(select(Sale.id)))
    assert client.get("/api/v1/catalog").status_code == 200
    assert client.post(f"/api/v1/imports/{batch_id}/commit", headers=ORIGIN).status_code == 410
    assert client.get(f"/api/v1/reports/{report_id}/download").status_code == 410
    with SessionLocal() as db:
        assert db.get(ImportBatch, batch_id).payload == []
        assert db.get(Report, report_id).rows == []
        assert list(db.scalars(select(Sale.id))) == sales_before


def test_session_expiry_and_pilot_admission_revocation(client, identity, monkeypatch):
    from datetime import timedelta

    register(client)
    with SessionLocal() as db:
        db.scalar(select(AccountSession)).expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/v1/account/profile").status_code == 401
    login_owner(client)
    monkeypatch.setattr(settings, "registration_allowlist", "other@example.test")
    assert client.get("/api/v1/account/profile").status_code == 403


def test_account_cap_and_login_rate_limit(client, identity, monkeypatch):
    register(client)
    monkeypatch.setattr(settings, "account_max_users", 1)
    assert (
        client.post(
            "/api/v1/auth/signup",
            headers=ORIGIN,
            json={"email": "member@example.test", "password": "fictional-test-passphrase"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/auth/verify",
            headers=ORIGIN,
            json={"email": "member@example.test", "token": "123456"},
        ).status_code
        == 429
    )
    for _ in range(8):
        assert (
            client.post(
                "/api/v1/auth/login",
                headers=ORIGIN,
                json={"email": "owner@example.test", "password": "invalid-fictional-passphrase"},
            ).status_code
            == 401
        )
    limited = client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": "owner@example.test", "password": "invalid-fictional-passphrase"},
    )
    assert limited.status_code == 429 and limited.headers["retry-after"] == "60"


def test_secure_cookie_and_session_cap(client, identity, monkeypatch):
    register(client)
    for _ in range(6):
        client.cookies.clear()
        login_owner(client)
    with SessionLocal() as db:
        assert len(list(db.scalars(select(AccountSession)))) == 5
    monkeypatch.setattr(settings, "account_cookie_secure", True)
    response = client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": "owner@example.test", "password": "fictional-test-passphrase"},
    )
    assert (
        "Secure" in response.headers["set-cookie"] and "HttpOnly" in response.headers["set-cookie"]
    )


def test_currency_integrity_and_selected_workspace_restored(client, fixture_data, identity):
    bind_fixture_account(client, fixture_data, "owner")
    assert (
        client.patch(
            "/api/v1/organizations/current",
            headers=ORIGIN,
            json={"name": "Existing currency", "currency": "USD"},
        ).status_code
        == 409
    )
    other = new_org(client, "Preferred fictional workspace")
    login_owner(client)
    assert client.get("/api/v1/organizations").json()["selected"] == other["id"]


def test_rejected_and_expired_invitation_tokens(client, identity):
    from datetime import timedelta
    from app.models import Invitation

    register(client)
    new_org(client)
    invitation, token = invite_member(client)
    register(client, "member@example.test")
    assert (
        client.post(
            "/api/v1/invitations/respond",
            headers=ORIGIN,
            json={"token": token, "decision": "reject"},
        ).json()["status"]
        == "rejected"
    )
    assert (
        client.post(
            "/api/v1/invitations/respond",
            headers=ORIGIN,
            json={"token": token, "decision": "accept"},
        ).status_code
        == 409
    )
    login_owner(client)
    invitation, token = invite_member(client)
    with SessionLocal() as db:
        db.get(Invitation, invitation["id"]).expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": "member@example.test", "password": "fictional-test-passphrase"},
    )
    assert (
        client.post(
            "/api/v1/invitations/respond",
            headers=ORIGIN,
            json={"token": token, "decision": "accept"},
        ).status_code
        == 409
    )


def test_provider_adapter_uses_fixed_https_project_and_sanitizes_errors(
    client, identity, monkeypatch
):
    import httpx
    from app.account_auth import SupabaseIdentity

    monkeypatch.setattr(settings, "supabase_url", "https://fixture.supabase.co")
    monkeypatch.setattr(settings, "supabase_publishable_key", "test-only-publishable")
    original_client = httpx.Client

    def handle(request):
        assert request.url.host == "fixture.supabase.co"
        assert request.headers["apikey"] == "test-only-publishable"
        assert request.headers["authorization"] == "Bearer test-only-access"
        return httpx.Response(
            401, json={"message": "sensitive provider diagnostic must not escape"}
        )

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handle), **kwargs),
    )
    with pytest.raises(HTTPException) as error:
        SupabaseIdentity().call("GET", "user", access="test-only-access")
    assert error.value.status_code == 401 and "sensitive" not in error.value.detail


def test_pkce_email_link_cookie_binding_and_single_use(client, identity):
    from app.models import IdentityChallenge

    data = {"email": "owner@example.test", "password": "fictional-test-passphrase"}
    signup = client.post("/api/v1/auth/signup", headers=ORIGIN, json=data)
    assert signup.status_code == 200 and "HttpOnly" in signup.headers["set-cookie"]
    saved = client.cookies.get("rp-auth-challenge")
    with SessionLocal() as db:
        row = db.scalar(select(IdentityChallenge))
        assert row.digest != saved and "code_verifier" not in row.verifier
    client.cookies.clear()
    assert (
        client.post(
            "/api/v1/auth/exchange", headers=ORIGIN, json={"code": "link-owner-signup"}
        ).status_code
        == 401
    )
    client.cookies.set("rp-auth-challenge", saved)
    result = client.post(
        "/api/v1/auth/exchange",
        headers=ORIGIN,
        json={"code": "link-owner-signup", "recovery": True},
    )
    assert result.status_code == 200 and result.json()["recovery"] is False
    client.cookies.set("rp-auth-challenge", saved)
    assert (
        client.post(
            "/api/v1/auth/exchange", headers=ORIGIN, json={"code": "link-owner-signup"}
        ).status_code
        == 401
    )


def test_pkce_recovery_expiry_and_server_owned_flow_type(client, identity):
    from app.models import IdentityChallenge
    from datetime import timedelta

    register(client)
    assert (
        client.post(
            "/api/v1/auth/recover", headers=ORIGIN, json={"email": "owner@example.test"}
        ).status_code
        == 200
    )
    with SessionLocal() as db:
        row = db.scalar(select(IdentityChallenge))
        row.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert (
        client.post(
            "/api/v1/auth/exchange", headers=ORIGIN, json={"code": "link-owner-recovery"}
        ).status_code
        == 401
    )
    client.post("/api/v1/auth/recover", headers=ORIGIN, json={"email": "owner@example.test"})
    verified = client.post(
        "/api/v1/auth/exchange", headers=ORIGIN, json={"code": "link-owner-recovery"}
    )
    assert verified.status_code == 200 and verified.json()["recovery"] is True
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            headers=ORIGIN,
            json={"password": "new-fictional-passphrase"},
        ).status_code
        == 200
    )


def test_open_registration_accepts_verified_non_allowlisted_identity(client, identity, monkeypatch):
    monkeypatch.setattr(settings, "registration_mode", "open")
    monkeypatch.setattr(settings, "email_delivery_configured", True)
    profile = register(client, "public@example.test")
    assert profile["email"] == "public@example.test"
    assert client.get("/api/v1/account/profile").status_code == 200
    monkeypatch.setattr(settings, "registration_enabled", False)
    # Existing members retain their access after new registration closes.
    assert client.get("/api/v1/account/profile").status_code == 200


def test_public_google_pkce_cookie_binding_replay_and_token_minimization(
    client, identity, monkeypatch
):
    from app.models import OAuthChallenge
    from app.account_auth import decrypted

    monkeypatch.setattr(settings, "registration_mode", "open")
    monkeypatch.setattr(settings, "google_auth_enabled", True)
    monkeypatch.setattr(settings, "supabase_url", "https://fixture.supabase.co")
    monkeypatch.setattr(settings, "supabase_publishable_key", "test-only-publishable")
    # Actual official SDK generates the Google URL and PKCE verifier.
    started = client.post("/api/v1/auth/google", headers=ORIGIN)
    assert started.status_code == 200
    assert "code_challenge=" in started.json()["url"]
    binding = client.cookies.get("rp-auth-challenge")
    with SessionLocal() as db:
        row = db.scalar(select(OAuthChallenge))
        verifier = decrypted(row.verifier)["code_verifier"]
        assert row.digest != binding and verifier not in started.text
    original = provider.call
    google_user = {
        "id": "verified-google-id",
        "email": "google-public@example.test",
        "email_confirmed_at": utcnow().isoformat(),
    }

    def call(method, path, body=None, access=None):
        if method == "GET" and path == "user" and access == "app-only-google-access":
            return google_user
        return original(method, path, body, access)

    def exchange(code, supplied):
        assert code == "google-single-use-code" and supplied == verifier
        return {
            "access_token": "app-only-google-access",
            "refresh_token": "app-only-refresh",
            "expires_in": 3600,
            "provider_token": "must-never-be-stored",
            "provider_refresh_token": "also-drop",
            "user": {"app_metadata": {"provider": "google", "providers": ["google"]}},
        }

    monkeypatch.setattr(provider, "call", call)
    monkeypatch.setattr(provider, "exchange", exchange)
    client.cookies.clear()
    assert (
        client.post(
            "/api/v1/auth/exchange", headers=ORIGIN, json={"code": "google-single-use-code"}
        ).status_code
        == 401
    )
    client.cookies.set("rp-auth-challenge", binding)
    verified = client.post(
        "/api/v1/auth/exchange",
        headers=ORIGIN,
        json={"code": "google-single-use-code", "recovery": True},
    )
    assert verified.status_code == 200 and not verified.json()["recovery"]
    assert verified.json()["profile"]["email"] == google_user["email"]
    with SessionLocal() as db:
        assert db.scalar(select(OAuthChallenge)) is None
        tokens = decrypted(db.scalar(select(AccountSession)).provider_tokens)
        assert "provider_token" not in tokens and "provider_refresh_token" not in tokens
    client.cookies.set("rp-auth-challenge", binding)
    assert (
        client.post(
            "/api/v1/auth/exchange", headers=ORIGIN, json={"code": "google-single-use-code"}
        ).status_code
        == 401
    )


def test_google_disabled_csrf_expiry_and_untrusted_identity(client, identity, monkeypatch):
    from app.models import OAuthChallenge
    from datetime import timedelta

    assert client.post("/api/v1/auth/google", headers=ORIGIN).status_code == 503
    monkeypatch.setattr(settings, "google_auth_enabled", True)
    monkeypatch.setattr(settings, "supabase_url", "https://fixture.supabase.co")
    monkeypatch.setattr(settings, "supabase_publishable_key", "test-only-publishable")
    assert client.post("/api/v1/auth/google").status_code == 403
    assert client.post("/api/v1/auth/google", headers=ORIGIN).status_code == 200
    with SessionLocal() as db:
        db.scalar(select(OAuthChallenge)).expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert (
        client.post(
            "/api/v1/auth/exchange", headers=ORIGIN, json={"code": "expired-google-code"}
        ).status_code
        == 401
    )
    assert client.post("/api/v1/auth/google", headers=ORIGIN).status_code == 200
    monkeypatch.setattr(
        provider, "exchange", lambda *_: {"user": {"app_metadata": {"provider": "email"}}}
    )
    assert (
        client.post(
            "/api/v1/auth/exchange", headers=ORIGIN, json={"code": "wrong-provider-code"}
        ).status_code
        == 403
    )


def test_public_email_registration_requires_delivery_configuration(client, identity, monkeypatch):
    monkeypatch.setattr(settings, "registration_mode", "open")
    monkeypatch.setattr(settings, "email_signup_enabled", False)
    assert (
        client.post(
            "/api/v1/auth/signup",
            headers=ORIGIN,
            json={"email": "public@example.test", "password": "fictional-passphrase"},
        ).status_code
        == 503
    )
    assert (
        client.post(
            "/api/v1/auth/recover", headers=ORIGIN, json={"email": "public@example.test"}
        ).status_code
        == 503
    )


def test_captcha_required_and_forwarded_only_to_managed_provider(client, identity, monkeypatch):
    monkeypatch.setattr(settings, "captcha_enabled", True)
    monkeypatch.setattr(settings, "captcha_site_key", "fictional-public-site-key")
    original = provider.call
    observed = []

    def capture(method, path, body=None, access=None):
        if method == "POST" and (path.startswith("signup") or path.startswith("token")):
            observed.append(body.get("gotrue_meta_security"))
        return original(method, path, body, access)

    monkeypatch.setattr(provider, "call", capture)
    data = {"email": "owner@example.test", "password": "fictional-test-passphrase"}
    assert client.post("/api/v1/auth/signup", headers=ORIGIN, json=data).status_code == 422
    data["captcha_token"] = "fictional-single-use-challenge-token"
    result = client.post("/api/v1/auth/signup", headers=ORIGIN, json=data)
    assert result.status_code == 200 and data["captcha_token"] not in result.text
    assert (
        client.post(
            "/api/v1/auth/verify",
            headers=ORIGIN,
            json={"email": data["email"], "token": "123456", "kind": "signup"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            headers=ORIGIN,
            json={"email": data["email"], "password": data["password"]},
        ).status_code
        == 422
    )
    assert client.post("/api/v1/auth/login", headers=ORIGIN, json=data).status_code == 200
    assert observed == [{"captcha_token": data["captcha_token"]}] * 2


def test_public_registration_configuration_fails_closed_without_delivery_and_captcha():
    from app.core import Settings
    from pydantic import ValidationError

    values = dict(
        _env_file=None,
        accounts_enabled=True,
        registration_enabled=True,
        registration_mode="open",
        supabase_url="https://fixture.supabase.co",
        supabase_publishable_key="test-only-publishable",
        session_encryption_key=Fernet.generate_key().decode(),
        public_demo=True,
        jwt_secret="test-only-stable-at-least-thirty-two-characters",
        erp_url="",
        database_url="postgresql+psycopg://localhost/fixture",
        app_origin="https://fixture.example.test",
        cors_origins="https://fixture.example.test",
    )
    with pytest.raises(ValidationError):
        Settings(**values)
    values.update(
        email_delivery_configured=True, captcha_enabled=True, captcha_site_key="test-only-site-key"
    )
    configured = Settings(**values)
    assert configured.registration_mode == "open" and not configured.registration_allowlist
