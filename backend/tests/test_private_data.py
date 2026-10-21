import io
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core import SessionLocal, settings
from app.demo import permitted_upload
from app.imports import read_file
from app.models import Membership, Organization, Product, SKU, Sale
from test_accounts import ORIGIN, identity, new_org, register  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
ROW = {"sku": "OWN-001", "product": "Fictional test product", "brand": "Test brand",
       "category": "Test category", "supplier": "Test supplier", "cost": "40.00",
       "price": "100.00", "lead_days": 7, "moq": 1, "pack_size": 1}


@pytest.mark.usefixtures("identity")
def test_private_catalog_import_and_date_driven_analytics(client, monkeypatch):
    register(client)
    org = new_org(client)
    assert client.patch("/api/v1/organizations/current", headers=ORIGIN,
                        json={"name": org["name"], "currency": "USD"}).status_code == 200
    monkeypatch.setattr(settings, "real_uploads_enabled", True)
    monkeypatch.setattr(settings, "public_demo", True)
    assert client.post("/api/v1/organizations/current/stores", headers=ORIGIN,
                       json={"code": "OWN01", "name": "Fictional own store"}).status_code == 200
    preview = client.post("/api/v1/organizations/current/catalog/preview", headers=ORIGIN,
                          files={"file": ("catalog.csv", (ROOT / "frontend/public/templates/catalog.csv").read_bytes(), "text/csv")})
    assert preview.status_code == 200, preview.text
    assert preview.json()["accepted"] == 1 and preview.json()["rejected"] == 0
    assert client.post("/api/v1/organizations/current/catalog", headers=ORIGIN,
                       json={"rows": [ROW]}).json() == {"created": 1}
    assert client.post("/api/v1/organizations/current/catalog", headers=ORIGIN,
                       json={"rows": [ROW]}).status_code == 409
    for kind in ("sales", "inventory"):
        source = (ROOT / f"frontend/public/templates/{kind}.csv").read_bytes()
        p = client.post(f"/api/v1/imports/preview?kind={kind}", headers=ORIGIN,
                        files={"file": (f"own-{kind}.csv", source, "text/csv")})
        assert p.status_code == 200, p.text
        assert p.json()["accepted"] == 1, p.text
        ident = p.json()["id"]
        assert client.post(f"/api/v1/imports/{ident}/validate", headers=ORIGIN,
                           json={"mapping": p.json()["mapping"]}).status_code == 200
        c = client.post(f"/api/v1/imports/{ident}/commit", headers=ORIGIN)
        assert c.status_code == 200, c.text
        assert client.post(f"/api/v1/imports/{ident}/commit", headers=ORIGIN).json()["idempotent_replay"]
    defaults = client.get("/api/v1/catalog").json()["default_filters"]
    assert defaults["end"] == "2026-10-22"
    analytics = client.get("/api/v1/analytics", params=defaults).json()
    assert analytics["metrics"]["revenue"] == 200
    assert analytics["metrics"]["gross_profit"] == 120
    assert analytics["data_label"] == "Organization workspace data"
    assert analytics["currency"] == "USD"
    report = client.post("/api/v1/reports", headers=ORIGIN, json={"kind": "Daily sales MIS"})
    assert report.status_code == 200 and report.json()["metrics"]["revenue"] == 200
    assert report.json()["filters"]["currency"] == "USD"
    analyst = client.post("/api/v1/analyst/query", headers=ORIGIN,
                          json={"question": "What is our current inventory value?"}).json()
    assert analyst["data_label"] == "Organization workspace data"
    assert analyst["rows"][0]["metric"].endswith("(USD)")
    assert analyst["rows"][0]["value"] == 400
    assert client.get("/api/v1/inventory", params=defaults).json()[0]["quantity"] == 10
    demo = client.post("/api/v1/demo/session").json()["access_token"]
    denied = client.post("/api/v1/imports/preview", headers={"Authorization": "Bearer " + demo},
                         files={"file": ("own.csv", (ROOT / "frontend/public/templates/sales.csv").read_bytes(), "text/csv")})
    assert denied.status_code == 403
    assert client.get("/api/v1/skus", headers={"Authorization": "Bearer " + demo}).json() == []
    assert org["id"] != client.get("/api/v1/me", headers={"Authorization": "Bearer " + demo}).json()["organization_id"]


@pytest.mark.usefixtures("identity")
def test_catalog_atomicity_scope_and_permissions(client, monkeypatch):
    register(client)
    org = new_org(client)
    assert client.post("/api/v1/organizations/current/catalog", headers=ORIGIN,
                       json={"rows": [ROW]}).status_code == 403
    monkeypatch.setattr(settings, "real_uploads_enabled", True)
    conflicting = {**ROW, "sku": "OWN-002", "lead_days": 99}
    assert client.post("/api/v1/organizations/current/catalog", headers=ORIGIN,
                       json={"rows": [ROW, conflicting]}).status_code == 409
    with SessionLocal() as db:
        assert not db.scalar(select(SKU.id)) and not db.scalar(select(Product.id))
        member = db.scalar(select(Membership).where(Membership.org_id == org["id"]))
        member.role = "analyst"
        db.commit()
    assert client.post("/api/v1/organizations/current/catalog", headers=ORIGIN,
                       json={"rows": [ROW]}).status_code == 403
    with SessionLocal() as db:
        db.scalar(select(Membership)).role = "owner"
        db.get(Organization, org["id"]).settings = {"_synthetic": True}
        db.commit()
    assert client.post("/api/v1/organizations/current/catalog", headers=ORIGIN,
                       json={"rows": [ROW]}).status_code == 409


@pytest.mark.usefixtures("identity")
def test_private_upload_limits_and_shared_capacity(client, monkeypatch):
    register(client)
    org = new_org(client)
    monkeypatch.setattr(settings, "real_uploads_enabled", True)
    monkeypatch.setattr(settings, "public_demo", True)
    with pytest.raises(HTTPException):
        permitted_upload(b"not-a-sample", private=False)
    permitted_upload(b"not-a-sample", private=True)
    with pytest.raises(HTTPException) as limit:
        read_file(b"a\n" + b"value\n" * 2001, "rows.csv", max_rows=2000)
    assert limit.value.status_code == 413
    from openpyxl import Workbook
    book = Workbook()
    book.active.append(["sku"])
    book.active.append(["=1+1"])
    stream = io.BytesIO()
    book.save(stream)
    with pytest.raises(HTTPException) as formulas:
        read_file(stream.getvalue(), "formula.xlsx", max_rows=500)
    assert formulas.value.status_code == 422
    from app.capacity import storage_budget
    with SessionLocal() as db:
        with pytest.raises(HTTPException) as capacity:
            storage_budget(db, sales=400001)
        assert capacity.value.status_code == 429
        assert not db.scalar(select(Sale.id).where(Sale.org_id == org["id"]))
