"""Reproducible fictional retail data. No customer or employee information."""

import random
from datetime import date, timedelta

from sqlalchemy import insert, select

from .models import (
    Brand,
    Category,
    Inventory,
    Product,
    SKU,
    Sale,
    StockMovement,
    Store,
    Supplier,
)

AS_OF = date(2026, 10, 18)
SEED = 271828


def seed(db, org_id):
    if db.scalar(select(Store.id).where(Store.org_id == org_id).limit(1)):
        return {"already_loaded": True}
    rng = random.Random(SEED)
    locations = [
        ("Ahmedabad", "CG Road"),
        ("Ahmedabad", "Satellite"),
        ("Ahmedabad", "Maninagar"),
        ("Surat", "Vesu"),
        ("Surat", "Adajan"),
        ("Vadodara", "Alkapuri"),
        ("Rajkot", "Kalawad Road"),
        ("Gandhinagar", "Infocity"),
        ("Mumbai", "Bandra"),
        ("Pune", "Aundh"),
        ("Jaipur", "C Scheme"),
        ("Indore", "Vijay Nagar"),
    ]
    stores = [
        Store(org_id=org_id, code=f"ST{i + 1:02}", name=f"{city} · {area}", city=city)
        for i, (city, area) in enumerate(locations)
    ]
    brands = [
        Brand(org_id=org_id, name=n)
        for n in ["Thread & Theory", "Morrow", "Aavya", "Northfield", "Everyday Co."]
    ]
    categories = [
        Category(org_id=org_id, name=n)
        for n in [
            "Shirts",
            "Trousers",
            "Ethnic wear",
            "Dresses",
            "T-shirts",
            "Outerwear",
        ]
    ]
    suppliers = [
        Supplier(org_id=org_id, name=n, lead_days=7 + i * 3, moq=6, pack_size=6)
        for i, n in enumerate(
            ["Loomline Textiles", "Westward Apparel", "Cottonworks", "Studio Supply"]
        )
    ]
    db.add_all(stores + brands + categories + suppliers)
    db.flush()
    products, skus = [], []
    for i in range(180):
        c = categories[i % 6]
        p = Product(
            org_id=org_id,
            name=f"{['Essential', 'Heritage', 'Relaxed', 'Classic', 'Signature', 'Weekend'][i % 6]} {c.name} {i + 1:03}",
            brand_id=brands[i % 5].id,
            category_id=c.id,
            supplier_id=suppliers[i % 4].id,
        )
        db.add(p)
        db.flush()
        products.append(p)
        price = rng.choice([799, 999, 1299, 1599, 1999, 2499])
        for v in range(2):
            skus.append(
                SKU(
                    org_id=org_id,
                    code=f"RP-{i + 1:03}-{v + 1}",
                    product_id=p.id,
                    size=["M", "L"][v],
                    color=["Ivory", "Indigo", "Sage", "Terracotta"][i % 4],
                    cost=round(price * 0.47, 2),
                    price=price,
                )
            )
    db.add_all(skus)
    db.flush()
    sales = []
    for offset in range(365):
        day = AS_OF - timedelta(days=364 - offset)
        seasonal = 1.6 if day.month in [10, 11] else (0.8 if day.month in [6, 7] else 1)
        for si, store in enumerate(stores):
            for j in range(
                round((15 + si % 4 * 3) * seasonal * (1.25 if day.weekday() >= 5 else 1))
            ):
                k = rng.randrange(len(skus))
                # Last twenty variants become inactive in the final quarter.
                if k >= 340 and offset >= 255:
                    k = rng.randrange(340)
                sku = skus[k]
                qty = rng.choice([1, 1, 1, 2, 3])
                if rng.random() < 0.035:
                    qty = -1
                discount = rng.choice([0, 0, 0.05, 0.10, 0.15])
                sales.append(
                    {
                        "org_id": org_id,
                        "transaction_id": f"DEMO-{offset}-{si}-{j}",
                        "date": day,
                        "store_id": store.id,
                        "sku_id": sku.id,
                        "quantity": qty,
                        "revenue": round(qty * float(sku.price) * (1 - discount), 2),
                        "cogs": round(qty * float(sku.cost), 2),
                    }
                )
    for start in range(0, len(sales), 5000):
        # RETURNING enables SQLAlchemy's paged insertmanyvalues path on psycopg,
        # avoiding one driver execution per synthetic transaction. Only IDs are
        # returned, in bounded batches; the generated business data is identical.
        db.execute(insert(Sale).returning(Sale.id), sales[start : start + 5000]).close()
    inventory = []
    for si, store in enumerate(stores):
        for k, sku in enumerate(skus):
            quantity = rng.randint(0, 2) if k % 19 == 0 else rng.randint(8, 40)
            if k >= 340:
                quantity = rng.randint(40, 95)
            inventory.append(
                {
                    "org_id": org_id,
                    "date": AS_OF,
                    "store_id": store.id,
                    "sku_id": sku.id,
                    "quantity": quantity,
                    "reserved": min(quantity, rng.randint(0, 2)),
                    "received_date": AS_OF
                    - timedelta(days=rng.randint(120, 240) if k >= 340 else rng.randint(7, 75)),
                }
            )
    db.execute(insert(Inventory).returning(Inventory.id), inventory).close()
    db.add_all(
        [
            StockMovement(
                org_id=org_id,
                store_id=s.id,
                sku_id=skus[0].id,
                quantity=24,
                kind="Demo receipt",
                reference="SEED-271828",
            )
            for s in stores
        ]
    )
    db.flush()
    return {
        "stores": 12,
        "brands": 5,
        "products": 180,
        "skus": 360,
        "sales": len(sales),
        "inventory_rows": len(inventory),
        "seed": SEED,
        "as_of": AS_OF.isoformat(),
    }
