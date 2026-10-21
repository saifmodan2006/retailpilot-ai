"""Private, owner-managed product setup for authorized retail extracts."""

from decimal import Decimal

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import func, select

from .accounts import DB
from .capacity import storage_budget
from .core import settings
from .imports import normalize, read_file
from .models import Brand, Category, Product, SKU, Supplier
from .organizations import actor, selected
from .workflows import audit

router = APIRouter(prefix="/api/v1/organizations/current/catalog")


class CatalogRow(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    sku: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    product: str = Field(min_length=1, max_length=120)
    brand: str = Field(min_length=1, max_length=80)
    category: str = Field(min_length=1, max_length=80)
    supplier: str = Field(min_length=1, max_length=80)
    cost: Decimal = Field(ge=0, le=10000000, max_digits=14, decimal_places=2)
    price: Decimal = Field(ge=0, le=10000000, max_digits=14, decimal_places=2)
    size: str = Field(default="", max_length=40)
    color: str = Field(default="", max_length=40)
    lead_days: int = Field(default=10, ge=0, le=365)
    moq: int = Field(default=1, ge=1, le=10000)
    pack_size: int = Field(default=1, ge=1, le=10000)

    @field_validator("product", "brand", "category", "supplier")
    @classmethod
    def visible_name(cls, value):
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError("Use a visible business name without control characters")
        return value


class CatalogBody(BaseModel):
    rows: list[CatalogRow] = Field(min_length=1, max_length=500)


def access(request, db):
    result = selected(request, db, ("owner", "admin"))
    if not settings.real_uploads_enabled:
        raise HTTPException(403, "Private data imports are not enabled.")
    if result[2].settings.get("_synthetic"):
        raise HTTPException(409, "Create an empty private workspace for your own data. Fictional samples stay separate.")
    return result


@router.post("/preview")
async def preview(request: Request, db: DB, file: UploadFile = File(...)):
    access(request, db)
    content = await file.read(1024 * 1024 + 1)
    raw, _ = read_file(content, file.filename or "", max_rows=500, max_bytes=1024 * 1024)
    rows, errors, seen = [], [], set()
    for source in raw:
        values = {normalize(k): v for k, v in source["values"].items() if v != ""}
        try:
            row = CatalogRow.model_validate(values)
            if row.sku in seen:
                raise ValueError("Duplicate SKU in this file")
            seen.add(row.sku)
            rows.append(row.model_dump(mode="json"))
        except (ValidationError, ValueError):
            errors.append({"sheet": source["sheet"], "row": source["row"],
                           "message": "Invalid catalog row. Check required fields, unique SKU codes, prices and supplier rules."})
    return {"rows": rows, "errors": errors, "accepted": len(rows), "rejected": len(errors)}


@router.post("")
def create(body: CatalogBody, request: Request, db: DB):
    _, _, org, member = access(request, db)
    storage_budget(db)
    codes = [r.sku for r in body.rows]
    if len(codes) != len(set(codes)) or db.scalar(
        select(SKU.id).where(SKU.org_id == org.id, SKU.code.in_(codes)).limit(1)
    ):
        raise HTTPException(409, "SKU codes must be new and unique within this workspace. No rows were added.")
    if (db.scalar(select(func.count()).select_from(SKU).where(SKU.org_id == org.id))
            + len(codes) > 1000
            or db.scalar(select(func.count()).select_from(SKU)) + len(codes) > 12000):
        raise HTTPException(429, "Catalog capacity reached. No rows were added.")
    references = {model: {r.name: r for r in db.scalars(select(model).where(model.org_id == org.id))}
                  for model in (Brand, Category, Supplier)}
    for row in body.rows:
        refs = []
        for model, name in [(Brand, row.brand), (Category, row.category), (Supplier, row.supplier)]:
            ref = references[model].get(name)
            rules = {k: getattr(row, k) for k in ("lead_days", "moq", "pack_size")}
            if ref and model is Supplier and any(getattr(ref, k) != v for k, v in rules.items()):
                raise HTTPException(409, "An existing supplier has different planning rules. Use matching rules or a different supplier name. No rows were added.")
            if not ref:
                ref = model(org_id=org.id, name=name, **(rules if model is Supplier else {}))
                db.add(ref)
                db.flush()
                references[model][name] = ref
            refs.append(ref.id)
        product = Product(org_id=org.id, name=row.product, brand_id=refs[0],
                          category_id=refs[1], supplier_id=refs[2])
        db.add(product)
        db.flush()
        db.add(SKU(org_id=org.id, code=row.sku, product_id=product.id, size=row.size,
                   color=row.color, cost=row.cost, price=row.price))
    audit(db, actor(db, member), "catalog.created", org.id, {"count": len(codes)})
    return {"created": len(codes)}
