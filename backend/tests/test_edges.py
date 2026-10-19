import io
from datetime import timedelta
from unittest.mock import patch

import httpx
import numpy as np
import pytest
from openpyxl import Workbook

from app.analytics import Filters, inventory_metrics
from app.core import SessionLocal
from app.forecasting import evaluate_series
from app.integrations import LocalERPAdapter
from app.mock_erp import app as mock_app
from app.models import Approval, Inventory, Organization, PurchaseOrder, Recommendation
from app.seed import AS_OF
from app.workflows import recommendations


def test_multisheet_and_optional_missing(client, fixture_data):
    wb = Workbook()
    for i, sheet in enumerate([wb.active, wb.create_sheet("Second")]):
        sheet.append(["transaction_id", "date", "store", "sku", "quantity", "unit_price"])
        sheet.append([f"MULTI-{i}", "18/10/2026", "ST01", "RP-001-1", 2, 100])
    stream = io.BytesIO()
    wb.save(stream)
    response = client.post(
        "/api/v1/imports/preview",
        headers=fixture_data["analyst"],
        files={"file": ("multi.xlsx", stream.getvalue())},
    )
    assert response.status_code == 200, response.text
    assert response.json()["accepted"] == 2
    assert {r["sheet"] for r in response.json()["preview"]} == {"Sheet", "Second"}


def test_inventory_update_and_latest_snapshot(client, fixture_data):
    headers = fixture_data["analyst"]
    content = b"date,store,sku,quantity,reserved,received_date\n2026-10-18,ST01,RP-001-1,20,2,2026-10-01\n2026-10-18,ST01,RP-002-1,-1,0,2026-01-01\n"
    batch = client.post(
        "/api/v1/imports/preview?kind=inventory",
        headers=headers,
        files={"file": ("stock.csv", content)},
    ).json()
    assert batch["accepted"] == 1 and batch["rejected"] == 1
    assert client.post(f"/api/v1/imports/{batch['id']}/commit", headers=headers).status_code == 200
    rows = client.get("/api/v1/inventory", headers=headers).json()
    active = next(r for r in rows if r["sku"] == "RP-001-1")
    assert active["available"] == 18 and active["cover_days"] == 9
    with SessionLocal() as db:
        db.add(
            Inventory(
                org_id=fixture_data["org"],
                date=AS_OF - timedelta(days=1),
                store_id=fixture_data["store"],
                sku_id=fixture_data["sku"],
                quantity=8,
                reserved=0,
                received_date=AS_OF - timedelta(days=10),
            )
        )
        db.commit()
        now = inventory_metrics(db, fixture_data["org"], Filters(), {})
        old = inventory_metrics(db, fixture_data["org"], Filters(end=AS_OF - timedelta(days=1)), {})
        assert next(r["quantity"] for r in now if r["sku"] == "RP-001-1") == 20
        assert next(r["quantity"] for r in old if r["sku"] == "RP-001-1") == 8


def test_only_confirmed_inbound_changes_reorder(client, fixture_data):
    with SessionLocal() as db:
        recommendations(db, fixture_data["org"], db.get(Organization, fixture_data["org"]).settings)
        rec = db.query(Recommendation).one()
        a = Approval(org_id=fixture_data["org"], recommendation_id=rec.id, requested_by=1)
        db.add(a)
        db.flush()
        order = PurchaseOrder(
            org_id=fixture_data["org"],
            approval_id=a.id,
            store_id=rec.store_id,
            sku_id=rec.sku_id,
            quantity=100,
            cost=4000,
            status="Simulated Draft",
        )
        db.add(order)
        db.flush()
        before = inventory_metrics(db, fixture_data["org"], Filters(), {})
        assert next(r for r in before if r["sku"] == "RP-001-1")["reorder_quantity"] == 30
        order.status = "Confirmed"
        db.flush()
        after = inventory_metrics(db, fixture_data["org"], Filters(), {})
        assert next(r for r in after if r["sku"] == "RP-001-1")["reorder_quantity"] == 0


def test_stale_approval_does_not_create_order(client, fixture_data):
    with SessionLocal() as db:
        recommendations(db, fixture_data["org"], db.get(Organization, fixture_data["org"]).settings)
        db.commit()
    rec = client.get("/api/v1/recommendations", headers=fixture_data["analyst"]).json()[0]
    a = client.post(
        f"/api/v1/recommendations/{rec['id']}/submit", headers=fixture_data["analyst"]
    ).json()
    with SessionLocal() as db:
        row = db.query(Inventory).filter(Inventory.sku_id == fixture_data["sku"]).one()
        row.quantity = 100
        db.commit()
    r = client.post(
        f"/api/v1/approvals/{a['id']}/decision",
        headers=fixture_data["manager"],
        json={"decision": "approve", "reason": "Reviewed"},
    )
    assert r.status_code == 409
    assert client.get("/api/v1/purchase-orders", headers=fixture_data["manager"]).json() == []


@pytest.mark.parametrize(
    "kind",
    [
        "Daily sales MIS",
        "Weekly store performance",
        "Monthly management summary",
        "Category sales analysis",
        "SKU inventory",
        "Low stock",
        "Dead stock and ageing",
        "Stock cover",
        "Working capital",
    ],
)
def test_all_report_types(client, fixture_data, kind):
    r = client.post("/api/v1/reports", headers=fixture_data["analyst"], json={"kind": kind})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["rows"]
    assert data["metrics"]["inventory_value"] == 5200
    file = client.get(
        f"/api/v1/reports/{data['id']}/download?format=pdf", headers=fixture_data["analyst"]
    )
    assert file.status_code == 200 and file.content.startswith(b"%PDF")


def test_forecast_backtest_origins_only_receive_past():
    observed = []
    from app.forecasting import predict as original

    def spy(values, model, horizon):
        observed.append((len(values), horizon))
        return original(values, model, horizon)

    with patch("app.forecasting.predict", side_effect=spy):
        evaluate_series(np.arange(90), 30)
    assert observed[:12] == [(69, 7), (76, 7), (83, 7)] * 4
    assert observed[-2:] == [(90, 30), (90, 30)]


def test_mock_erp_auth_and_pagination():
    from fastapi.testclient import TestClient

    with TestClient(mock_app) as c:
        assert c.get("/sales").status_code == 401
        response = c.get(
            "/sales?page=0&page_size=10", headers={"Authorization": "Bearer local-simulator-only"}
        )
        assert len(response.json()["items"]) == 10
        assert response.json()["next_page"] == 1
        assert (
            c.get(
                "/sales?page=2&page_size=10",
                headers={"Authorization": "Bearer local-simulator-only"},
            ).json()["next_page"]
            is None
        )


def test_http_adapter_error_and_mapping():
    adapter = LocalERPAdapter()
    requests = []

    def handler(request):
        requests.append(request)
        page = int(request.url.params["page"])
        return httpx.Response(
            200, json={"items": [{"page": page}], "next_page": 1 if page == 0 else None}
        )

    original = httpx.Client
    with patch(
        "app.integrations.httpx.Client",
        side_effect=lambda **kw: original(transport=httpx.MockTransport(handler), **kw),
    ):
        rows = adapter.fetch_products()
    assert rows == [{"page": 0}, {"page": 1}]
    assert requests[0].headers["Authorization"] == "Bearer local-simulator-only"
    content = adapter.map_sales(
        [
            {
                "reference": "ERP-1",
                "sold_on": "2026-10-18",
                "location": "ST01",
                "item_code": "RP-001-1",
                "units": 2,
                "price_inr": 100,
            }
        ]
    )
    assert b"ERP-1,2026-10-18,ST01,RP-001-1,2,100,0" in content
    assert adapter.preview_updates(rows)["writes_executed"] is False
