import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import analyst, imports
from .demo import admit_session, demo_only, permitted_upload, quota
from .ingress import BodyLimitMiddleware, DemoResourceMiddleware
from .analytics import Filters, analytics, catalog, inventory_metrics, records
from .core import SessionLocal, get_db, settings, utcnow
from .forecasting import forecast
from .models import (
    Approval,
    AuditEvent,
    Brand,
    Category,
    ForecastResult,
    ImportBatch,
    Organization,
    Product,
    PurchaseOrder,
    Recommendation,
    Report,
    SKU,
    Store,
    Supplier,
    User,
    ValidationError,
    Workflow,
)
from .reports import REPORT_TYPES, create_report, pdf_export, xlsx_export
from .security import current_user, manager, rate_limit, token
from .seed import AS_OF, seed
from .workflows import (
    audit,
    execute,
    recommendation_values,
    recommendations,
    transition,
)


@asynccontextmanager
async def lifespan(app):
    # A process restart makes interrupted jobs explicitly retryable, not silently complete.
    with SessionLocal() as db:
        for row in db.scalars(select(Workflow).where(Workflow.status == "Running")):
            row.status, row.error = (
                "Failed",
                "Worker interrupted. Safe retry is available.",
            )
        db.commit()
    yield


app = FastAPI(
    title="RetailPilot AI",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if settings.public_demo else "/docs",
    redoc_url=None,
    openapi_url=None if settings.public_demo else "/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-RP-CSRF"],
)
app.add_middleware(BodyLimitMiddleware)
app.add_middleware(DemoResourceMiddleware)
from .accounts import router as accounts_router  # noqa: E402

app.include_router(accounts_router)
from .organizations import router as organizations_router  # noqa: E402

app.include_router(organizations_router)
from .team import router as team_router  # noqa: E402

app.include_router(team_router)
DB = Annotated[Session, Depends(get_db, scope="function")]
Actor = Annotated[User, Depends(current_user)]
Manager = Annotated[User, Depends(manager)]
Scope = Annotated[Filters, Query()]


@app.middleware("http")
async def log_requests(request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = (
        "no-store" if request.url.path.startswith("/api/") else "no-cache"
    )
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; "
        "object-src 'none'; frame-ancestors 'none'; base-uri 'self'"
    )
    if request.url.path == "/docs":
        del response.headers["Content-Security-Policy"]
    logging.info(
        "method=%s path=%s status=%s duration_ms=%s",
        request.method,
        request.url.path,
        response.status_code,
        round((time.monotonic() - start) * 1000),
    )
    return response


@app.exception_handler(IntegrityError)
async def integrity_error(request, exc):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=409,
        content={
            "detail": "A concurrent or duplicate action was prevented. Refresh and try again."
        },
    )


def owned(db, model, ident, org, lock=False):
    query = select(model).where(model.id == ident, model.org_id == org)
    row = db.scalar(query.with_for_update() if lock else query)
    if not row:
        raise HTTPException(404, "Record not found")
    return row


def serialize(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns if c.name != "payload"}


def config(db, user):
    return db.get(Organization, user.org_id).settings


@app.get("/api/v1/health")
def health(db: DB):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "version": "1.0.0", "demo": settings.demo_enabled}


@app.post("/api/v1/demo/session")
def demo_session(request: Request, db: DB):
    if not settings.demo_enabled:
        raise HTTPException(
            403,
            "Demo sessions disabled. Configure an organizational identity provider for production.",
        )
    rate_limit(request, "demo", 6)
    admit_session(db)
    org = Organization(id=str(uuid.uuid4()), name="Threadline Retail · Demo", is_demo=True)
    db.add(org)
    db.flush()
    user = User(org_id=org.id, name="Demo analyst", role="analyst")
    db.add(user)
    db.flush()
    audit(db, user, "session.created", org.id)
    return {
        "access_token": token(user),
        "user": serialize(user),
        "organization": org.name,
        "as_of": str(AS_OF),
    }


@app.get("/api/v1/me")
def me(user: Actor, db: DB):
    org = db.get(Organization, user.org_id)
    return {
        "user": serialize(user),
        "organization": org.name,
        "organization_id": org.id,
        "currency": org.settings.get("currency", "INR"),
        "timezone": org.settings.get("timezone", "Asia/Kolkata"),
        "is_demo": org.is_demo,
        "demo": settings.demo_enabled and org.is_demo,
        "public_demo": settings.public_demo,
    }


@app.post("/api/v1/demo/end")
def end_demo(user: Actor, db: DB):
    if not settings.demo_enabled:
        raise HTTPException(403, "Demo mode is disabled")
    org = demo_only(db, user)
    org.settings = {**org.settings, "_demo_ended": True}
    audit(db, user, "session.ended", org.id)
    return {"ended": True}


@app.post("/api/v1/demo/role")
def demo_role(user: Actor, db: DB):
    if not settings.demo_enabled:
        raise HTTPException(403, "Role switching is restricted to synthetic demo environments")
    demo_only(db, user)
    user.role = "manager" if user.role == "analyst" else "analyst"
    user.name = "Demo " + user.role
    audit(db, user, "demo.role_changed", user.id)
    return {"access_token": token(user), "user": serialize(user)}


@app.post("/api/v1/demo/seed")
def demo_seed(user: Actor, db: DB):
    if not settings.demo_enabled:
        raise HTTPException(403, "Demo seeding disabled")
    demo_only(db, user)
    # Lock the tenant to serialize simultaneous seeds on PostgreSQL.
    db.scalar(select(Organization).where(Organization.id == user.org_id).with_for_update())
    result = seed(db, user.org_id)
    count = recommendations(db, user.org_id, config(db, user))
    audit(db, user, "demo.loaded", user.org_id, result)
    return {**result, "recommendations_created": count}


@app.get("/api/v1/catalog")
def get_catalog(user: Actor, db: DB):
    return {
        "stores": [
            serialize(r) for r in db.scalars(select(Store).where(Store.org_id == user.org_id))
        ],
        "categories": [
            serialize(r) for r in db.scalars(select(Category).where(Category.org_id == user.org_id))
        ],
        "brands": [
            serialize(r) for r in db.scalars(select(Brand).where(Brand.org_id == user.org_id))
        ],
        "skus": records(catalog(db, user.org_id)),
    }


@app.get("/api/v1/analytics")
def get_analytics(user: Actor, db: DB, filters: Scope):
    return analytics(db, user.org_id, filters, config(db, user))


@app.get("/api/v1/inventory")
def get_inventory(user: Actor, db: DB, filters: Scope):
    return inventory_metrics(db, user.org_id, filters, config(db, user))


@app.get("/api/v1/imports")
def get_imports(user: Actor, db: DB):
    return [
        serialize(r)
        for r in db.scalars(
            select(ImportBatch)
            .where(ImportBatch.org_id == user.org_id)
            .order_by(ImportBatch.id.desc())
        )
    ]


def batch_result(db, batch):
    return {
        **serialize(batch),
        "columns": sorted({c for r in batch.payload for c in r["values"]}),
        "preview": batch.payload[:8],
        "errors": [
            serialize(r)
            for r in db.scalars(
                select(ValidationError).where(
                    ValidationError.batch_id == batch.id,
                    ValidationError.org_id == batch.org_id,
                )
            )
        ],
    }


@app.post("/api/v1/imports/preview")
async def preview_upload(
    user: Actor,
    db: DB,
    file: UploadFile = File(...),
    kind: Literal["sales", "inventory"] = "sales",
):
    content = await file.read(8 * 1024 * 1024 + 1)
    from .models import Membership

    private = bool(db.scalar(select(Membership.id).where(Membership.actor_id == user.id)))
    permitted_upload(content, private=private)
    quota(db, user, ImportBatch, 12)
    batch = imports.preview(db, user.org_id, content, file.filename or "", kind)
    if private and len(batch.payload) > 2000:
        raise HTTPException(413, "Private pilot imports support at most 2,000 rows per file.")
    audit(
        db,
        user,
        "import.previewed",
        batch.id,
        {"accepted": batch.accepted, "rejected": batch.rejected},
    )
    return batch_result(db, batch)


class MappingBody(BaseModel):
    mapping: dict[str, str]


@app.post("/api/v1/imports/{ident}/validate")
def validate_mapping(ident: int, body: MappingBody, user: Actor, db: DB):
    batch = owned(db, ImportBatch, ident, user.org_id)
    if batch.status == "Expired":
        raise HTTPException(
            410, "The preview expired under the seven-day retention policy. Upload a fresh file."
        )
    allowed = imports.SALES_FIELDS if batch.kind == "sales" else imports.INVENTORY_FIELDS
    if (
        len(body.mapping) > 50
        or any(v and v not in allowed for v in body.mapping.values())
        or len([v for v in body.mapping.values() if v])
        != len(set(v for v in body.mapping.values() if v))
    ):
        raise HTTPException(422, "Mappings must use unique supported fields")
    imports.revalidate(db, batch, body.mapping)
    return batch_result(db, batch)


@app.post("/api/v1/imports/{ident}/commit")
def commit(ident: int, user: Actor, db: DB, background: BackgroundTasks):
    batch = owned(db, ImportBatch, ident, user.org_id, lock=True)
    if batch.status == "Expired":
        raise HTTPException(410, "The preview expired. Upload a fresh file.")
    from .models import Membership, Sale, Inventory
    from sqlalchemy import func

    if (
        db.scalar(select(Membership.id).where(Membership.actor_id == user.id))
        and batch.status != "Imported"
    ):
        db.scalar(select(Organization).where(Organization.id == user.org_id).with_for_update())
        model, maximum = (Sale, 100000) if batch.kind == "sales" else (Inventory, 10000)
        count = db.scalar(
            select(func.count()).select_from(model).where(model.org_id == user.org_id)
        )
        if count + batch.accepted > maximum:
            raise HTTPException(429, "Workspace row quota reached. No data was imported.")
    changed = imports.commit_import(db, batch)
    if changed:
        audit(
            db,
            user,
            "import.committed",
            batch.id,
            {"accepted": batch.accepted, "rejected": batch.rejected},
        )
        workflow = Workflow(
            org_id=user.org_id,
            kind="daily-report" if batch.kind == "sales" else "low-stock",
            key=f"import:{batch.id}",
        )
        db.add(workflow)
        db.commit()
        background.add_task(execute, workflow.id)
    return {**serialize(batch), "idempotent_replay": not changed}


@app.get("/api/v1/imports/{ident}/errors.xlsx")
def export_errors(ident: int, user: Actor, db: DB):
    batch = owned(db, ImportBatch, ident, user.org_id)
    errors = [
        {"sheet": r.sheet, "row": r.row, "message": r.message}
        for r in db.scalars(
            select(ValidationError).where(
                ValidationError.batch_id == batch.id,
                ValidationError.org_id == user.org_id,
            )
        )
    ]
    return download(xlsx_export("Validation report", errors), "validation-errors.xlsx")


@app.get("/api/v1/recommendations")
def get_recommendations(user: Actor, db: DB):
    return [
        {
            **serialize(r),
            "sku": sku.code,
            "product": product.name,
            "category_id": product.category_id,
            "brand_id": product.brand_id,
            "store": store.name,
        }
        for r, sku, store, product in db.execute(
            select(Recommendation, SKU, Store, Product)
            .join(SKU, Recommendation.sku_id == SKU.id)
            .join(Store, Recommendation.store_id == Store.id)
            .join(Product, SKU.product_id == Product.id)
            .where(Recommendation.org_id == user.org_id)
            .order_by(Recommendation.cost.desc())
        )
    ]


@app.post("/api/v1/recommendations/{ident}/submit")
def submit_approval(ident: int, user: Actor, db: DB):
    quota(db, user, Approval, 30)
    quota(db, user, Workflow, 60)
    rec = owned(db, Recommendation, ident, user.org_id, lock=True)
    if rec.status != "Suggested":
        raise HTTPException(409, "Only suggested recommendations may be submitted")
    # Recompute before submission; stale suggestions cannot silently become purchase drafts.
    matching = next(
        (
            r
            for r in inventory_metrics(db, user.org_id, Filters(), config(db, user))
            if r["store_id"] == rec.store_id and r["sku_id"] == rec.sku_id
        ),
        None,
    )
    if not matching or matching["reorder_quantity"] <= 0:
        raise HTTPException(409, "Recommendation no longer meets reorder rules")
    for field, value in recommendation_values(matching).items():
        setattr(rec, field, value)
    approval = Approval(org_id=user.org_id, recommendation_id=rec.id, requested_by=user.id)
    db.add(approval)
    rec.status = "Awaiting Approval"
    db.add(
        Workflow(
            org_id=user.org_id,
            key=f"approval:{rec.id}",
            kind="purchase-approval",
            status="Awaiting Approval",
            result={"recommendation_id": rec.id},
        )
    )
    audit(db, user, "approval.requested", rec.id)
    db.flush()
    return serialize(approval)


@app.get("/api/v1/approvals")
def get_approvals(user: Actor, db: DB):
    return [
        {
            **serialize(a),
            "recommendation": serialize(r),
            "sku": s.code,
            "store": st.name,
        }
        for a, r, s, st in db.execute(
            select(Approval, Recommendation, SKU, Store)
            .join(Recommendation, Approval.recommendation_id == Recommendation.id)
            .join(SKU, Recommendation.sku_id == SKU.id)
            .join(Store, Recommendation.store_id == Store.id)
            .where(Approval.org_id == user.org_id)
            .order_by(Approval.id.desc())
        )
    ]


class DecisionBody(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=3, max_length=1000)


@app.post("/api/v1/approvals/{ident}/decision")
def decision(ident: int, body: DecisionBody, user: Manager, db: DB):
    a = owned(db, Approval, ident, user.org_id, lock=True)
    if a.status != "Awaiting Approval":
        raise HTTPException(409, "This request has already been reviewed")
    rec = owned(db, Recommendation, a.recommendation_id, user.org_id)
    if body.decision == "approve":
        matching = next(
            (
                r
                for r in inventory_metrics(db, user.org_id, Filters(), config(db, user))
                if r["store_id"] == rec.store_id and r["sku_id"] == rec.sku_id
            ),
            None,
        )
        if (
            not matching
            or matching["reorder_quantity"] != rec.quantity
            or round(matching["cost"] * matching["reorder_quantity"], 2) != float(rec.cost)
        ):
            raise HTTPException(
                409,
                "Planning evidence changed. Reject this request and run low-stock detection to create a fresh recommendation.",
            )
    a.status = "Completed" if body.decision == "approve" else "Rejected"
    a.reason, a.reviewed_by, a.reviewed_at = body.reason, user.id, utcnow()
    rec.status = "Approved" if body.decision == "approve" else "Rejected"
    workflow = db.scalar(
        select(Workflow).where(Workflow.org_id == user.org_id, Workflow.key == f"approval:{rec.id}")
    )
    transition(workflow, a.status)
    if body.decision == "approve":
        db.add(
            PurchaseOrder(
                org_id=user.org_id,
                approval_id=a.id,
                store_id=rec.store_id,
                sku_id=rec.sku_id,
                quantity=rec.quantity,
                cost=rec.cost,
            )
        )
    audit(
        db,
        user,
        "approval." + body.decision,
        a.id,
        {"reason": body.reason, "simulated": True},
    )
    return serialize(a)


@app.get("/api/v1/purchase-orders")
def purchase_orders(user: Actor, db: DB):
    return [
        serialize(r)
        for r in db.scalars(select(PurchaseOrder).where(PurchaseOrder.org_id == user.org_id))
    ]


class ForecastFilters(Filters):
    horizon: int = Field(default=30, ge=7, le=30)


@app.get("/api/v1/forecasts")
def get_forecast(user: Actor, db: DB, filters: Annotated[ForecastFilters, Query()]):
    if filters.horizon not in [7, 30]:
        raise HTTPException(422, "Forecast horizon must be 7 or 30 days")
    result = forecast(db, user.org_id, filters, filters.horizon)
    if user.role == "viewer":
        return result
    previous = db.scalar(
        select(ForecastResult)
        .where(ForecastResult.org_id == user.org_id)
        .order_by(ForecastResult.id.desc())
        .limit(1)
    )
    if (
        previous
        and previous.filters == filters.model_dump(mode="json")
        and previous.result == result
    ):
        return result
    quota(db, user, ForecastResult, 30)
    db.add(
        ForecastResult(
            org_id=user.org_id,
            version=result["version"],
            filters=filters.model_dump(mode="json"),
            result=result,
        )
    )
    return result


@app.get("/api/v1/reports")
def get_reports(user: Actor, db: DB):
    return [
        serialize(r) | {"rows": None}
        for r in db.scalars(
            select(Report).where(Report.org_id == user.org_id).order_by(Report.id.desc()).limit(100)
        )
    ]


class ReportBody(BaseModel):
    kind: str
    filters: Filters = Field(default_factory=Filters)


@app.post("/api/v1/reports")
def generate_report(body: ReportBody, user: Actor, db: DB):
    if body.kind not in REPORT_TYPES:
        raise HTTPException(422, "Unsupported report type")
    quota(db, user, Report, 30)
    report = create_report(db, user.org_id, body.kind, body.filters, config(db, user))
    audit(
        db,
        user,
        "report.generated",
        report.id,
        {"kind": body.kind, "filters": report.filters},
    )
    return serialize(report)


def download(content, filename):
    return Response(
        content,
        media_type="application/pdf"
        if filename.endswith(".pdf")
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/v1/reports/{ident}/download")
def get_report_file(ident: int, user: Actor, db: DB, format: Literal["xlsx", "pdf"] = "xlsx"):
    report = owned(db, Report, ident, user.org_id)
    from .account_auth import aware
    from datetime import timedelta

    if not db.get(Organization, user.org_id).is_demo and aware(
        report.created_at
    ) < utcnow() - timedelta(days=30):
        raise HTTPException(
            410,
            "The generated artifact expired under the thirty-day retention policy. Generate a new report.",
        )
    audit(db, user, "report.downloaded", ident, {"format": format})
    return download(
        pdf_export(report)
        if format == "pdf"
        else xlsx_export(report.kind, report.rows, report.metrics, report.filters),
        f"retailpilot-{ident}.{format}",
    )


class QuestionBody(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    filters: Filters = Field(default_factory=Filters)


@app.get("/api/v1/analyst/questions")
def questions(user: Actor):
    return analyst.QUESTIONS


@app.post("/api/v1/analyst/query")
def query_analyst(body: QuestionBody, user: Actor, db: DB):
    result = analyst.answer(db, user.org_id, body.question, body.filters, config(db, user))
    audit(db, user, "analyst.queried", result["tool"])
    return result


@app.get("/api/v1/workflows")
def get_workflows(user: Actor, db: DB):
    return [
        serialize(r)
        for r in db.scalars(
            select(Workflow)
            .where(Workflow.org_id == user.org_id)
            .order_by(Workflow.id.desc())
            .limit(100)
        )
    ]


class WorkflowBody(BaseModel):
    kind: Literal["daily-report", "weekly-mis", "low-stock"]
    key: str = Field(min_length=3, max_length=100)


@app.post("/api/v1/workflows")
def run_workflow(body: WorkflowBody, user: Actor, db: DB, background: BackgroundTasks):
    if (
        body.kind == "low-stock"
        and user.role == "analyst"
        and not db.get(Organization, user.org_id).is_demo
    ):
        from .models import Membership

        if db.scalar(select(Membership.id).where(Membership.actor_id == user.id)):
            raise HTTPException(403, "Inventory automation requires a manager, admin or owner.")
    existing = db.scalar(
        select(Workflow).where(Workflow.org_id == user.org_id, Workflow.key == body.key)
    )
    if existing:
        return serialize(existing)
    quota(db, user, Workflow, 30)
    row = Workflow(org_id=user.org_id, kind=body.kind, key=body.key)
    db.add(row)
    db.flush()
    audit(db, user, "workflow.queued", row.id)
    db.commit()
    background.add_task(execute, row.id)
    return serialize(row)


@app.post("/api/v1/workflows/{ident}/retry")
def retry_workflow(ident: int, user: Actor, db: DB, background: BackgroundTasks):
    row = owned(db, Workflow, ident, user.org_id, lock=True)
    if (
        row.kind == "low-stock"
        and user.role == "analyst"
        and not db.get(Organization, user.org_id).is_demo
    ):
        from .models import Membership

        if db.scalar(select(Membership.id).where(Membership.actor_id == user.id)):
            raise HTTPException(403, "Inventory automation requires a manager, admin or owner.")
    if row.attempts >= 3:
        raise HTTPException(409, "Maximum three attempts reached")
    transition(row, "Pending")
    audit(db, user, "workflow.retried", ident)
    db.commit()
    background.add_task(execute, row.id)
    return serialize(row)


@app.post("/api/v1/workflows/{ident}/cancel")
def cancel_workflow(ident: int, user: Actor, db: DB):
    row = owned(db, Workflow, ident, user.org_id, lock=True)
    if (
        row.kind == "low-stock"
        and user.role == "analyst"
        and not db.get(Organization, user.org_id).is_demo
    ):
        from .models import Membership

        if db.scalar(select(Membership.id).where(Membership.actor_id == user.id)):
            raise HTTPException(403, "Inventory automation requires a manager, admin or owner.")
    if row.kind == "purchase-approval":
        raise HTTPException(
            409, "Purchase approval workflows must be reviewed in the Approval Center"
        )
    transition(row, "Cancelled")
    audit(db, user, "workflow.cancelled", ident)
    return serialize(row)


@app.get("/api/v1/audit")
def audit_events(user: Actor, db: DB):
    return [
        serialize(r)
        for r in db.scalars(
            select(AuditEvent)
            .where(AuditEvent.org_id == user.org_id)
            .order_by(AuditEvent.id.desc())
            .limit(250)
        )
    ]


class SettingsBody(BaseModel):
    safety_days: int = Field(ge=0, le=60)
    dead_days: int = Field(ge=30, le=365)
    cover_days: int = Field(ge=1, le=90)


@app.get("/api/v1/settings")
def get_settings(user: Actor, db: DB):
    return {
        "planning": config(db, user),
        "as_of": str(AS_OF),
        "llm_enabled": settings.llm_enabled and bool(settings.llm_api_key),
        "timezone": "Asia/Kolkata",
        "currency": "INR",
        "demo": settings.demo_enabled,
    }


@app.patch("/api/v1/settings")
def update_settings(body: SettingsBody, user: Manager, db: DB):
    org = db.get(Organization, user.org_id)
    org.settings = {**org.settings, **body.model_dump()}
    # Rebuild unsubmitted suggestions using current rules; pending approvals stay reviewable.
    db.query(Recommendation).filter(
        Recommendation.org_id == user.org_id, Recommendation.status == "Suggested"
    ).delete()
    recommendations(db, user.org_id, body.model_dump())
    audit(db, user, "settings.updated", user.org_id, body.model_dump())
    return body


@app.get("/api/v1/stores")
def stores(user: Actor, db: DB):
    return [serialize(r) for r in db.scalars(select(Store).where(Store.org_id == user.org_id))]


@app.get("/api/v1/products")
def products(user: Actor, db: DB):
    return [serialize(r) for r in db.scalars(select(Product).where(Product.org_id == user.org_id))]


@app.get("/api/v1/skus")
def skus(user: Actor, db: DB):
    return records(catalog(db, user.org_id))


@app.get("/api/v1/suppliers")
def suppliers(user: Actor, db: DB):
    return [
        serialize(r) for r in db.scalars(select(Supplier).where(Supplier.org_id == user.org_id))
    ]


class SupplierPlanningBody(BaseModel):
    lead_days: int = Field(ge=1, le=180)
    moq: int = Field(ge=1, le=10000)
    pack_size: int = Field(ge=1, le=1000)


@app.patch("/api/v1/suppliers/{ident}")
def update_supplier(ident: int, body: SupplierPlanningBody, user: Manager, db: DB):
    supplier = owned(db, Supplier, ident, user.org_id)
    for key, value in body.model_dump().items():
        setattr(supplier, key, value)
    db.flush()
    db.query(Recommendation).filter(
        Recommendation.org_id == user.org_id, Recommendation.status == "Suggested"
    ).delete()
    recommendations(db, user.org_id, config(db, user))
    audit(db, user, "supplier.planning_updated", ident, body.model_dump())
    return serialize(supplier)


@app.get("/api/v1/integrations/erp/status")
def erp_status(user: Actor):
    from .integrations import LocalERPAdapter

    try:
        products = LocalERPAdapter().fetch_products()
        return {
            "connected": True,
            "products": len(products),
            "message": f"Authenticated and paginated {len(products)} independent fictional products.",
        }
    except Exception:
        return {
            "connected": False,
            "message": "Local simulator unavailable. Start app.mock_erp on port 8001, or use Docker Compose.",
        }


@app.post("/api/v1/integrations/erp/sync")
def erp_sync(user: Actor, db: DB):
    from .integrations import LocalERPAdapter

    adapter = LocalERPAdapter()
    quota(db, user, ImportBatch, 12)
    try:
        rows = adapter.fetch_sales()
        content = adapter.map_sales(rows)
    except Exception as exc:
        raise HTTPException(
            502,
            "ERP synchronization failed. Check simulator URL, authentication and response mapping.",
        ) from exc
    batch = imports.preview(db, user.org_id, content, "erp-sales.csv", "sales")
    audit(db, user, "erp.previewed", batch.id, {"rows": len(rows), "committed": False})
    return batch_result(db, batch)


@app.get("/api/v1/imports/{ident}")
def get_import(ident: int, user: Actor, db: DB):
    return batch_result(db, owned(db, ImportBatch, ident, user.org_id))


from pathlib import Path  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

sample_path = Path(__file__).resolve().parents[2] / "sample_data"
if sample_path.exists():
    app.mount("/samples", StaticFiles(directory=str(sample_path)), name="samples")

# Optional same-origin production bundle. API routes always take precedence.
web_path = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if web_path.exists():
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=str(web_path / "assets")), name="assets")
    app.mount("/product", StaticFiles(directory=str(web_path / "product")), name="product")

    @app.get("/{path:path}", include_in_schema=False)
    def web_app(path: str):
        if path.startswith(("api/", "samples/", "assets/", "product/")):
            raise HTTPException(404, "Not found")
        if path not in ("", "app", "onboarding", "privacy") and not path.startswith(
            ("app/", "auth/", "onboarding/", "privacy/")
        ):
            raise HTTPException(404, "Not found")
        return FileResponse(web_path / "index.html")
