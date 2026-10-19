"""Independent fictional HTTP dataset, not the application's database."""

import os
import secrets

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

app = FastAPI(title="Local ERP simulator")
expected = os.getenv("ERP_TOKEN", "local-simulator-only")


def auth(authorization: str = Header("")):
    if not secrets.compare_digest(authorization, "Bearer " + expected):
        raise HTTPException(401, "Invalid ERP simulator token")


DATA = {
    "products": [
        {
            "item_code": f"RP-{i:03}-1",
            "description": f"Independent ERP apparel {i}",
            "price_inr": 999,
        }
        for i in range(1, 26)
    ],
    "inventory": [
        {
            "item_code": f"RP-{i:03}-1",
            "location": "ST01",
            "units": i + 5,
            "as_of": "2026-10-18",
        }
        for i in range(1, 26)
    ],
    "sales": [
        {
            "reference": f"ERP-DEMO-{i:03}",
            "sold_on": "2026-10-18",
            "location": f"ST{(i % 3) + 1:02}",
            "item_code": f"RP-{i:03}-1",
            "units": 2,
            "price_inr": 999,
            "discount_fraction": 0,
        }
        for i in range(1, 26)
    ],
}


@app.get("/health")
def health():
    return {"status": "ok", "simulator": True}


@app.get("/{resource}", dependencies=[Depends(auth)])
def fetch(resource: str, page: int = Query(0, ge=0), page_size: int = Query(10, ge=1, le=50)):
    if resource not in DATA:
        raise HTTPException(404, "Unknown ERP resource")
    start = page * page_size
    return {
        "items": DATA[resource][start : start + page_size],
        "next_page": page + 1 if start + page_size < len(DATA[resource]) else None,
    }


class Transactions(BaseModel):
    rows: list[dict] = Field(max_length=1000)


@app.post("/transactions", dependencies=[Depends(auth)])
def import_transactions(body: Transactions):
    # Explicit simulator receipt only. Never a commercial ERP write.
    return {"simulated": True, "received": len(body.rows), "persistent_writes": False}
