import io
from datetime import timedelta

import jwt
import pytest
from fastapi import HTTPException
from openpyxl import Workbook

from app.core import SessionLocal, Settings, settings, utcnow
from app.demo import admit_session, permitted_upload
from app.imports import parse_date, read_file
from app.models import Organization, Workflow
from app.security import rate_limit
from starlette.requests import Request


def test_tokens_require_expiry_issuer_and_audience(client, fixture_data):
    for claims in [
        {"sub": "1", "org": "tenant-a"},
        {
            "sub": "1",
            "org": "tenant-a",
            "exp": utcnow() - timedelta(hours=1),
            "iat": utcnow() - timedelta(hours=2),
            "iss": "retailpilot",
            "aud": "retailpilot-api",
        },
        {
            "sub": "1",
            "org": "tenant-a",
            "exp": utcnow() + timedelta(hours=1),
            "iat": utcnow(),
            "iss": "other",
            "aud": "retailpilot-api",
        },
    ]:
        encoded = jwt.encode(claims, settings.jwt_secret, algorithm="HS256")
        assert (
            client.get("/api/v1/me", headers={"Authorization": "Bearer " + encoded}).status_code
            == 401
        )
    assert (
        client.get("/api/v1/me", headers={"Authorization": "Bearer malformed"}).status_code == 401
    )


def test_role_switch_cannot_escalate_private_tenant(client, fixture_data):
    assert client.post("/api/v1/demo/role", headers=fixture_data["analyst"]).status_code == 403
    assert client.post("/api/v1/demo/seed", headers=fixture_data["analyst"]).status_code == 403
    session = client.post("/api/v1/demo/session").json()
    assert (
        client.post(
            "/api/v1/demo/role", headers={"Authorization": "Bearer " + session["access_token"]}
        ).json()["user"]["role"]
        == "manager"
    )


def test_public_mode_excludes_private_and_expired_tenants(client, fixture_data, monkeypatch):
    monkeypatch.setattr(settings, "public_demo", True)
    assert client.get("/api/v1/analytics", headers=fixture_data["analyst"]).status_code == 403
    with SessionLocal() as db:
        org = db.get(Organization, fixture_data["org"])
        org.is_demo = True
        org.created_at = utcnow() - timedelta(hours=3)
        db.commit()
    assert client.get("/api/v1/analytics", headers=fixture_data["analyst"]).status_code == 403


def test_public_sample_only_uploads(monkeypatch):
    monkeypatch.setattr(settings, "public_demo", True)
    with pytest.raises(HTTPException) as exc:
        permitted_upload(b"private business extract")
    assert exc.value.status_code == 403
    from pathlib import Path

    permitted_upload(
        (Path(__file__).resolve().parents[2] / "sample_data/sales_import.xlsx").read_bytes()
    )


def test_demo_capacity_and_expired_cleanup_keep_private_data(client, fixture_data, monkeypatch):
    monkeypatch.setattr(settings, "public_demo", True)
    monkeypatch.setattr(settings, "demo_max_tenants", 1)
    with SessionLocal() as db:
        db.add(
            Organization(
                id="expired-demo",
                name="Expired",
                is_demo=True,
                created_at=utcnow() - timedelta(hours=3),
            )
        )
        db.add(Organization(id="active-demo", name="Active", is_demo=True))
        db.commit()
        with pytest.raises(HTTPException) as exc:
            admit_session(db)
        assert exc.value.status_code == 429
        assert db.get(Organization, "tenant-a") is not None
        assert db.get(Organization, "expired-demo") is None


def test_body_limit_before_parser_and_cors(client, fixture_data):
    r = client.post(
        "/api/v1/imports/preview",
        headers={**fixture_data["analyst"], "Content-Length": str(10 * 1024 * 1024)},
        content=b"",
    )
    assert r.status_code == 413
    r = client.options(
        "/api/v1/analytics",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert r.status_code == 400 and "access-control-allow-origin" not in r.headers
    r = client.options(
        "/api/v1/analytics",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert (
        client.get("/api/v1/analytics", headers=fixture_data["analyst"]).headers["cache-control"]
        == "no-store"
    )


def test_formulas_and_expansion_and_row_limits():
    wb = Workbook()
    ws = wb.active
    ws.append(["sku", "quantity"])
    ws.append(["RP-001-1", "=2+2"])
    stream = io.BytesIO()
    wb.save(stream)
    with pytest.raises(HTTPException) as exc:
        read_file(stream.getvalue(), "formula.xlsx")
    assert exc.value.status_code == 422 and "Formula" in exc.value.detail
    with pytest.raises(HTTPException) as exc:
        read_file(b"sku,quantity\n" + b"RP-001-1,1\n" * 20001, "big.csv")
    assert exc.value.status_code == 413


@pytest.mark.parametrize(
    "value", ["2026-10-18garbage", "2026-10-18T14:00:00Z", "tomorrow", "18/99/2026"]
)
def test_strict_business_date(value):
    with pytest.raises(ValueError):
        parse_date(value)


def test_money_product_cannot_overflow(client, fixture_data):
    content = b"transaction_id,date,store,sku,quantity,unit_price\nOVER,2026-10-18,ST01,RP-001-1,1000000,10000000\n"
    r = client.post(
        "/api/v1/imports/preview",
        headers=fixture_data["analyst"],
        files={"file": ("overflow.csv", content)},
    )
    assert r.status_code == 200 and r.json()["accepted"] == 0
    assert "monetary range" in r.json()["errors"][0]["message"]


def test_rate_limit_and_approval_cancellation_guard(client, fixture_data):
    request = Request({"type": "http", "client": ("test-ip", 1)})
    rate_limit(request, "test", 1)
    with pytest.raises(HTTPException) as exc:
        rate_limit(request, "test", 1)
    assert exc.value.status_code == 429 and exc.value.headers["Retry-After"] == "60"
    with SessionLocal() as db:
        row = Workflow(
            org_id=fixture_data["org"],
            kind="purchase-approval",
            key="guard",
            status="Awaiting Approval",
        )
        db.add(row)
        db.commit()
        ident = row.id
    assert (
        client.post(
            f"/api/v1/workflows/{ident}/cancel", headers=fixture_data["manager"]
        ).status_code
        == 409
    )


def test_public_config_fails_closed():
    base = dict(
        _env_file=None,
        public_demo=True,
        jwt_secret="x" * 40,
        database_url="postgresql+psycopg://demo:placeholder@db/demo",
        erp_url="",
    )
    assert Settings(**base).public_demo
    for override in [
        {"llm_enabled": True},
        {"llm_api_key": "not-a-real-key"},
        {"erp_url": "https://private.example"},
        {"cors_origins": "*"},
        {"database_url": "sqlite:///test.db"},
    ]:
        with pytest.raises(ValueError):
            Settings(**(base | override))


def test_ambiguous_csv_headers_are_rejected_before_pandas():
    for header in [b"sku,sku\na,b\n", b"sku,SKU code\na,b\n"]:
        with pytest.raises(HTTPException) as exc:
            read_file(header, "ambiguous.csv")
        assert exc.value.status_code == 422


def test_neon_url_normalization_and_tls_requirement():
    url = "postgresql://demo:placeholder@demo-pooler.example.neon.tech/demo"
    base = dict(_env_file=None, public_demo=True, jwt_secret="x" * 40, erp_url="")
    with pytest.raises(ValueError):
        Settings(**base, database_url=url)
    configured = Settings(**base, database_url=url + "?sslmode=require")
    assert configured.database_url.startswith("postgresql+psycopg://")
