"""Generate and ship a complete independent, reproducible fictional CSV archive."""

import csv
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core import Base  # noqa: E402
from app.models import (
    Brand,
    Category,
    Inventory,
    Organization,
    Product,
    SKU,
    Sale,
    Store,
    Supplier,
)  # noqa: E402
from app.seed import seed  # noqa: E402

with tempfile.TemporaryDirectory() as directory:
    engine = create_engine("sqlite:///" + str(Path(directory) / "sample.db"))
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Organization(id="export-demo", name="Fictional Threadline Retail"))
        db.commit()
        result = seed(db, "export-demo")
        db.commit()
        stores = {r.id: r.code for r in db.scalars(select(Store))}
        skus = {r.id: r.code for r in db.scalars(select(SKU))}
        products = {r.id: r for r in db.scalars(select(Product))}
        brands = {r.id: r.name for r in db.scalars(select(Brand))}
        categories = {r.id: r.name for r in db.scalars(select(Category))}
        suppliers = {r.id: r for r in db.scalars(select(Supplier))}
        tables = {
            "stores.csv": [
                {"store": r.code, "name": r.name, "city": r.city}
                for r in db.scalars(select(Store))
            ],
            "catalog.csv": [
                {
                    "sku": r.code,
                    "product": products[r.product_id].name,
                    "brand": brands[products[r.product_id].brand_id],
                    "category": categories[products[r.product_id].category_id],
                    "supplier": suppliers[products[r.product_id].supplier_id].name,
                    "size": r.size,
                    "color": r.color,
                    "cost": float(r.cost),
                    "price": float(r.price),
                }
                for r in db.scalars(select(SKU))
            ],
            "sales.csv": [
                {
                    "transaction_id": r.transaction_id,
                    "date": str(r.date),
                    "store": stores[r.store_id],
                    "sku": skus[r.sku_id],
                    "quantity": r.quantity,
                    "unit_price": round(float(r.revenue) / r.quantity, 2),
                    "discount": 0,
                }
                for r in db.scalars(select(Sale))
            ],
            "inventory.csv": [
                {
                    "date": str(r.date),
                    "store": stores[r.store_id],
                    "sku": skus[r.sku_id],
                    "quantity": r.quantity,
                    "reserved": r.reserved,
                    "received_date": str(r.received_date),
                }
                for r in db.scalars(select(Inventory))
            ],
            "suppliers.csv": [
                {
                    "name": r.name,
                    "lead_days": r.lead_days,
                    "moq": r.moq,
                    "pack_size": r.pack_size,
                }
                for r in suppliers.values()
            ],
        }
        with zipfile.ZipFile(
            ROOT / "sample_data/demo_dataset.zip", "w", zipfile.ZIP_DEFLATED
        ) as archive:
            for filename, rows in tables.items():
                output = io.StringIO(newline="")
                writer = csv.DictWriter(output, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
                info = zipfile.ZipInfo(filename, date_time=(2026, 10, 18, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, output.getvalue().encode("utf-8"))
        (ROOT / "sample_data/manifest.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        print(json.dumps(result))
    engine.dispose()
