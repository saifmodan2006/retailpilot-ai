"""A bounded, provider-independent ERP contract and local HTTP implementation."""

import csv
import io
from typing import Protocol

import httpx

from .core import settings


class ERPAdapter(Protocol):
    def fetch_products(self) -> list[dict]: ...
    def fetch_inventory(self) -> list[dict]: ...
    def fetch_sales(self) -> list[dict]: ...
    def import_transactions(self, rows: list[dict]) -> dict: ...
    def preview_updates(self, rows: list[dict]) -> dict: ...


class LocalERPAdapter:
    def __init__(self):
        self.url, self.token = settings.erp_url, settings.erp_token

    def fetch(self, resource):
        rows, cursor = [], 0
        with httpx.Client(
            base_url=self.url,
            timeout=8,
            headers={"Authorization": "Bearer " + self.token},
        ) as client:
            for _ in range(100):
                response = client.get("/" + resource, params={"page": cursor, "page_size": 10})
                response.raise_for_status()
                data = response.json()
                if not isinstance(data.get("items"), list):
                    raise ValueError("ERP response has no item list")
                rows.extend(data["items"])
                if data.get("next_page") is None:
                    return rows
                cursor = int(data["next_page"])
        raise ValueError("ERP pagination exceeded safe limit")

    def fetch_products(self):
        return self.fetch("products")

    def fetch_inventory(self):
        return self.fetch("inventory")

    def fetch_sales(self):
        return self.fetch("sales")

    def import_transactions(self, rows):
        with httpx.Client(timeout=8) as client:
            response = client.post(
                self.url + "/transactions",
                headers={"Authorization": "Bearer " + self.token},
                json={"rows": rows},
            )
            response.raise_for_status()
            return response.json()

    def preview_updates(self, rows):
        return {
            "mode": "preview-only",
            "count": len(rows),
            "proposed": rows,
            "writes_executed": False,
        }

    @staticmethod
    def map_sales(rows):
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "transaction_id",
                "date",
                "store",
                "sku",
                "quantity",
                "unit_price",
                "discount",
            ],
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(
                {
                    "transaction_id": r["reference"],
                    "date": r["sold_on"],
                    "store": r["location"],
                    "sku": r["item_code"],
                    "quantity": r["units"],
                    "unit_price": r["price_inr"],
                    "discount": r.get("discount_fraction", 0),
                }
            )
        return output.getvalue().encode()
