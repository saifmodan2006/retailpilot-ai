import os
import tempfile
from datetime import timedelta

import pytest

TEST_DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_URL"] = "sqlite:///" + TEST_DB
os.environ["JWT_SECRET"] = "test-only-secret-at-least-thirty-two-characters"

from fastapi.testclient import TestClient  # noqa: E402
from app.core import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
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
    User,
)  # noqa: E402
from app.security import attempts, token  # noqa: E402
from app.seed import AS_OF  # noqa: E402


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    attempts.clear()
    with TestClient(app) as client:
        yield client


@pytest.fixture
def fixture_data(client):
    with SessionLocal() as db:
        org = Organization(id="tenant-a", name="Fixture Retail")
        other = Organization(id="tenant-b", name="Other Retail")
        db.add_all([org, other])
        db.flush()
        user = User(org_id=org.id, name="Analyst", role="analyst")
        manager = User(org_id=org.id, name="Manager", role="manager")
        outsider = User(org_id=other.id, name="Other manager", role="manager")
        store = Store(org_id=org.id, code="ST01", name="Fixture Store", city="Ahmedabad")
        cat = Category(org_id=org.id, name="Shirts")
        brand = Brand(org_id=org.id, name="Fixture Brand")
        supplier = Supplier(
            org_id=org.id, name="Fixture Supplier", lead_days=10, moq=6, pack_size=6
        )
        db.add_all([user, manager, outsider, store, cat, brand, supplier])
        db.flush()
        product = Product(
            org_id=org.id,
            name="Fixture Shirt",
            brand_id=brand.id,
            category_id=cat.id,
            supplier_id=supplier.id,
        )
        db.add(product)
        db.flush()
        sku = SKU(
            org_id=org.id,
            code="RP-001-1",
            product_id=product.id,
            size="M",
            color="Ivory",
            cost=40,
            price=100,
        )
        dead = SKU(
            org_id=org.id,
            code="RP-002-1",
            product_id=product.id,
            size="L",
            color="Ivory",
            cost=50,
            price=120,
        )
        db.add_all([sku, dead])
        db.flush()
        for i in range(90):
            db.add(
                Sale(
                    org_id=org.id,
                    transaction_id=f"FIX-{i}",
                    date=AS_OF - timedelta(days=i),
                    store_id=store.id,
                    sku_id=sku.id,
                    quantity=2,
                    revenue=180,
                    cogs=80,
                )
            )
        db.add(
            Sale(
                org_id=org.id,
                transaction_id="RETURN",
                date=AS_OF,
                store_id=store.id,
                sku_id=sku.id,
                quantity=-1,
                revenue=-90,
                cogs=-40,
            )
        )
        db.add_all(
            [
                Inventory(
                    org_id=org.id,
                    date=AS_OF,
                    store_id=store.id,
                    sku_id=sku.id,
                    quantity=5,
                    reserved=1,
                    received_date=AS_OF - timedelta(days=20),
                ),
                Inventory(
                    org_id=org.id,
                    date=AS_OF,
                    store_id=store.id,
                    sku_id=dead.id,
                    quantity=100,
                    reserved=0,
                    received_date=AS_OF - timedelta(days=150),
                ),
            ]
        )
        db.commit()
        return {
            "analyst": {"Authorization": "Bearer " + token(user)},
            "manager": {"Authorization": "Bearer " + token(manager)},
            "outsider": {"Authorization": "Bearer " + token(outsider)},
            "store": store.id,
            "sku": sku.id,
            "org": org.id,
        }
