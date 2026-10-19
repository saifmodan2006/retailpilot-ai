from datetime import date, timedelta

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, cast, Float

from .models import (
    Brand,
    Category,
    Inventory,
    Product,
    PurchaseOrder,
    SKU,
    Sale,
    Store,
    Supplier,
)
from .seed import AS_OF


class Filters(BaseModel):
    start: date = AS_OF - timedelta(days=29)
    end: date = AS_OF
    store_id: int | None = Field(default=None, gt=0)
    category_id: int | None = Field(default=None, gt=0)
    brand_id: int | None = Field(default=None, gt=0)
    sku_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def range_valid(self):
        if self.start > self.end or (self.end - self.start).days > 1095:
            raise ValueError("Date range must be ordered and at most three years")
        return self


def catalog(db, org):
    rows = (
        db.execute(
            select(
                SKU.id.label("sku_id"),
                SKU.code.label("sku"),
                SKU.size,
                SKU.color,
                SKU.cost,
                SKU.price,
                Product.name.label("product"),
                Product.category_id,
                Product.brand_id,
                Category.name.label("category"),
                Brand.name.label("brand"),
                Supplier.lead_days,
                Supplier.moq,
                Supplier.pack_size,
            )
            .join(Product, SKU.product_id == Product.id)
            .join(Category, Product.category_id == Category.id)
            .join(Brand, Product.brand_id == Brand.id)
            .join(Supplier, Product.supplier_id == Supplier.id)
            .where(SKU.org_id == org)
        )
        .mappings()
        .all()
    )
    return pd.DataFrame([dict(r) for r in rows])


def frames(db, org, f):
    cat = catalog(db, org)
    if cat.empty:
        return pd.DataFrame(), pd.DataFrame()
    for field in ["category_id", "brand_id", "sku_id"]:
        value = getattr(f, field)
        if value:
            cat = cat[cat[field] == value]
    sales = pd.DataFrame.from_records(
        db.execute(
            select(
                Sale.date,
                Sale.store_id,
                Sale.sku_id,
                Sale.quantity,
                cast(Sale.revenue, Float).label("revenue"),
                cast(Sale.cogs, Float).label("cogs"),
            ).where(
                Sale.org_id == org,
                Sale.date <= f.end,
                Sale.sku_id.in_(cat.sku_id.tolist()),
                *([Sale.store_id == f.store_id] if f.store_id else []),
            )
        ).all(),
        columns=["date", "store_id", "sku_id", "quantity", "revenue", "cogs"],
    )
    inv = pd.DataFrame.from_records(
        db.execute(
            select(
                Inventory.date,
                Inventory.store_id,
                Inventory.sku_id,
                Inventory.quantity,
                Inventory.reserved,
                Inventory.received_date,
            ).where(
                Inventory.org_id == org,
                Inventory.date <= f.end,
                Inventory.sku_id.in_(cat.sku_id.tolist()),
                *([Inventory.store_id == f.store_id] if f.store_id else []),
            )
        ).all(),
        columns=["date", "store_id", "sku_id", "quantity", "reserved", "received_date"],
    )
    stores = pd.DataFrame(
        [
            dict(r)
            for r in db.execute(
                select(Store.id.label("store_id"), Store.name.label("store"), Store.city).where(
                    Store.org_id == org
                )
            ).mappings()
        ]
    )
    if not sales.empty:
        sales = sales.merge(cat, on="sku_id").merge(stores, on="store_id")
        for col in ["revenue", "cogs", "cost", "price"]:
            sales[col] = sales[col].astype(float)
    if not inv.empty:
        inv = (
            inv.sort_values("date")
            .drop_duplicates(["store_id", "sku_id"], keep="last")
            .merge(cat, on="sku_id")
            .merge(stores, on="store_id")
        )
        inv["cost"] = inv["cost"].astype(float)
    if f.store_id:
        if not sales.empty:
            sales = sales[sales.store_id == f.store_id]
        if not inv.empty:
            inv = inv[inv.store_id == f.store_id]
    return sales, inv


def records(frame):
    return (
        frame.replace([np.inf, -np.inf], np.nan)
        .astype(object)
        .where(pd.notna(frame), None)
        .to_dict("records")
    )


def inventory_metrics(db, org, f, config, data_frames=None):
    sales, inv = data_frames if data_frames is not None else frames(db, org, f)
    if inv.empty:
        return []
    recent = sales[sales.date >= f.end - timedelta(days=29)] if not sales.empty else sales
    if not recent.empty:
        demand = (
            recent.assign(positive=recent.quantity.clip(lower=0))
            .groupby(["store_id", "sku_id"])
            .positive.sum()
            .rename("demand_30")
        )
        inv = inv.join(demand, on=["store_id", "sku_id"])
    else:
        inv["demand_30"] = 0
    inv["demand_30"] = inv.demand_30.fillna(0)
    if not sales.empty:
        last = (
            sales[sales.quantity > 0].groupby(["store_id", "sku_id"]).date.max().rename("last_sale")
        )
        inv = inv.join(last, on=["store_id", "sku_id"])
    else:
        inv["last_sale"] = None
    inv["daily_demand"] = inv.demand_30 / 30
    inv["high_demand"] = (inv.demand_30 >= inv.demand_30.quantile(0.9)) & (inv.demand_30 > 0)
    inv["available"] = (inv.quantity - inv.reserved).clip(lower=0)
    inv["cover_days"] = inv.available / inv.daily_demand.replace(0, np.nan)
    inv["value"] = inv.quantity * inv.cost
    inv["age_days"] = inv.received_date.map(lambda d: (f.end - d).days)
    inv["ageing"] = (inv.age_days >= 90) & (inv.quantity > 0)
    inv["inactive_days"] = [
        (f.end - d).days if pd.notna(d) else age for d, age in zip(inv.last_sale, inv.age_days)
    ]
    inv["dead_stock"] = (inv.inactive_days >= config.get("dead_days", 90)) & (inv.quantity > 0)
    inv["classification"] = np.select(
        [
            inv.dead_stock,
            inv.cover_days.fillna(999) < config.get("cover_days", 14),
            inv.cover_days.fillna(999) > 90,
            inv.cover_days.fillna(999) > 60,
        ],
        ["Dead stock", "Low stock", "Overstock", "Slow moving"],
        default="Healthy",
    )
    inbound = db.execute(
        select(PurchaseOrder.store_id, PurchaseOrder.sku_id, PurchaseOrder.quantity).where(
            PurchaseOrder.org_id == org, PurchaseOrder.status == "Confirmed"
        )
    ).all()
    inbound_map = {}
    for store, sku, qty in inbound:
        inbound_map[(store, sku)] = inbound_map.get((store, sku), 0) + qty
    inv["inbound"] = [inbound_map.get((s, k), 0) for s, k in zip(inv.store_id, inv.sku_id)]
    inv["safety_stock"] = np.ceil(inv.daily_demand * config.get("safety_days", 7)).astype(int)
    inv["reorder_point"] = np.ceil(inv.daily_demand * inv.lead_days + inv.safety_stock).astype(int)
    raw = (inv.reorder_point - inv.available - inv.inbound).clip(lower=0)
    inv["reorder_quantity"] = [
        int(np.ceil(max(q, moq) / pack) * pack) if q > 0 else 0
        for q, moq, pack in zip(raw, inv.moq, inv.pack_size)
    ]
    inv["last_sale"] = inv.last_sale.map(lambda d: d.isoformat() if pd.notna(d) else None)
    inv["date"] = inv.date.map(str)
    inv["received_date"] = inv.received_date.map(str)
    return records(inv)


def analytics(db, org, f, config):
    history, inv = frames(db, org, f)
    sales = history[history.date >= f.start].copy() if not history.empty else history
    inventory = inventory_metrics(db, org, f, config, (history, inv.copy()))
    revenue = float(sales.revenue.sum()) if not sales.empty else 0
    cogs = float(sales.cogs.sum()) if not sales.empty else 0
    units = int(sales.quantity.sum()) if not sales.empty else 0
    stock = sum(r["quantity"] for r in inventory)
    demand = sum(r["daily_demand"] for r in inventory)
    available = sum(r["available"] for r in inventory)
    metrics = {
        "revenue": round(revenue, 2),
        "units": units,
        "gross_profit": round(revenue - cogs, 2),
        "margin": round((revenue - cogs) / revenue * 100, 2) if revenue else 0,
        "stock": stock,
        "inventory_value": round(sum(r["value"] for r in inventory), 2),
        "sell_through": round(max(units, 0) / (max(units, 0) + stock) * 100, 2)
        if max(units, 0) + stock
        else 0,
        "cover_days": round(available / demand, 1) if demand else None,
        "low_stock": sum(r["classification"] == "Low stock" for r in inventory),
        "dead_stock_value": round(sum(r["value"] for r in inventory if r["dead_stock"]), 2),
        "forecasted_stockouts": sum(
            r["cover_days"] is not None and r["cover_days"] < 14 for r in inventory
        ),
    }
    trend, stores, categories, products = [], [], [], []
    if not sales.empty:
        sales["date"] = sales.date.map(str)
        trend = records(
            sales.groupby("date", as_index=False).agg(
                revenue=("revenue", "sum"), units=("quantity", "sum")
            )
        )
        stores = records(
            sales.groupby(["store_id", "store"], as_index=False)
            .agg(
                revenue=("revenue", "sum"),
                units=("quantity", "sum"),
                cogs=("cogs", "sum"),
            )
            .sort_values("revenue", ascending=False)
        )
        categories = records(
            sales.groupby("category", as_index=False).agg(
                revenue=("revenue", "sum"), units=("quantity", "sum")
            )
        )
        products = records(
            sales.groupby(["sku", "product", "brand", "category"], as_index=False)
            .agg(revenue=("revenue", "sum"), units=("quantity", "sum"))
            .sort_values("revenue", ascending=False)
            .head(50)
        )
    return {
        "metrics": metrics,
        "trend": trend,
        "stores": stores,
        "categories": categories,
        "products": products,
        "filters": f.model_dump(mode="json"),
        "data_label": "Synthetic demonstration data",
        "inventory_as_of": str(inv.date.max()) if not inv.empty else None,
    }
