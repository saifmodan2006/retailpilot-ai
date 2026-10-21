from datetime import date, datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .core import Base, utcnow


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str]
    is_demo: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    settings: Mapped[dict] = mapped_column(
        JSON, default=lambda: {"safety_days": 7, "dead_days": 90, "cover_days": 14}
    )


class TenantRow:
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(TenantRow, Base):
    __tablename__ = "users"
    name: Mapped[str]
    role: Mapped[str] = mapped_column(default="analyst")


class Store(TenantRow, Base):
    __tablename__ = "stores"
    code: Mapped[str]
    name: Mapped[str]
    city: Mapped[str]
    __table_args__ = (UniqueConstraint("org_id", "code"),)


class Brand(TenantRow, Base):
    __tablename__ = "brands"
    name: Mapped[str]
    __table_args__ = (UniqueConstraint("org_id", "name"),)


class Category(TenantRow, Base):
    __tablename__ = "categories"
    name: Mapped[str]
    __table_args__ = (UniqueConstraint("org_id", "name"),)


class Supplier(TenantRow, Base):
    __tablename__ = "suppliers"
    name: Mapped[str]
    lead_days: Mapped[int] = mapped_column(default=10)
    moq: Mapped[int] = mapped_column(default=6)
    pack_size: Mapped[int] = mapped_column(default=6)


class Product(TenantRow, Base):
    __tablename__ = "products"
    name: Mapped[str]
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))


class SKU(TenantRow, Base):
    __tablename__ = "skus"
    code: Mapped[str]
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    size: Mapped[str]
    color: Mapped[str]
    cost: Mapped[float] = mapped_column(Numeric(14, 2))
    price: Mapped[float] = mapped_column(Numeric(14, 2))
    __table_args__ = (UniqueConstraint("org_id", "code"),)


class Sale(TenantRow, Base):
    __tablename__ = "sales"
    transaction_id: Mapped[str]
    date: Mapped[date]
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    sku_id: Mapped[int] = mapped_column(ForeignKey("skus.id"))
    quantity: Mapped[int]
    revenue: Mapped[float] = mapped_column(Numeric(14, 2))
    cogs: Mapped[float] = mapped_column(Numeric(14, 2))
    __table_args__ = (
        UniqueConstraint("org_id", "transaction_id"),
        Index("ix_sales_scope_date", "org_id", "date"),
    )


class Inventory(TenantRow, Base):
    __tablename__ = "inventory_snapshots"
    date: Mapped[date]
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    sku_id: Mapped[int] = mapped_column(ForeignKey("skus.id"))
    quantity: Mapped[int]
    reserved: Mapped[int] = mapped_column(default=0)
    received_date: Mapped[date]
    __table_args__ = (UniqueConstraint("org_id", "store_id", "sku_id", "date"),)


class StockMovement(TenantRow, Base):
    __tablename__ = "stock_movements"
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    sku_id: Mapped[int] = mapped_column(ForeignKey("skus.id"))
    quantity: Mapped[int]
    kind: Mapped[str]
    reference: Mapped[str]


class ImportBatch(TenantRow, Base):
    __tablename__ = "import_batches"
    fingerprint: Mapped[str]
    filename: Mapped[str]
    kind: Mapped[str]
    status: Mapped[str] = mapped_column(default="Preview")
    accepted: Mapped[int] = mapped_column(default=0)
    rejected: Mapped[int] = mapped_column(default=0)
    payload: Mapped[list] = mapped_column(JSON, default=list)
    mapping: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("org_id", "fingerprint"),)


class ValidationError(TenantRow, Base):
    __tablename__ = "validation_errors"
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"))
    row: Mapped[int]
    sheet: Mapped[str]
    message: Mapped[str]


class Recommendation(TenantRow, Base):
    __tablename__ = "recommendations"
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    sku_id: Mapped[int] = mapped_column(ForeignKey("skus.id"))
    quantity: Mapped[int]
    cost: Mapped[float] = mapped_column(Numeric(14, 2))
    severity: Mapped[str]
    rationale: Mapped[str]
    evidence: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(default="Suggested")


class Approval(TenantRow, Base):
    __tablename__ = "approvals"
    recommendation_id: Mapped[int] = mapped_column(ForeignKey("recommendations.id"), unique=True)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(default="Awaiting Approval")
    reason: Mapped[str] = mapped_column(default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PurchaseOrder(TenantRow, Base):
    __tablename__ = "purchase_orders"
    approval_id: Mapped[int] = mapped_column(ForeignKey("approvals.id"), unique=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    sku_id: Mapped[int] = mapped_column(ForeignKey("skus.id"))
    quantity: Mapped[int]
    cost: Mapped[float] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(default="Simulated Draft")


class StockTransfer(TenantRow, Base):
    __tablename__ = "stock_transfers"
    from_store: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    to_store: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    sku_id: Mapped[int] = mapped_column(ForeignKey("skus.id"))
    quantity: Mapped[int]
    status: Mapped[str] = mapped_column(default="Proposed")


class ForecastResult(TenantRow, Base):
    __tablename__ = "forecast_results"
    version: Mapped[str]
    filters: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)


class Workflow(TenantRow, Base):
    __tablename__ = "workflow_executions"
    kind: Mapped[str]
    key: Mapped[str]
    status: Mapped[str] = mapped_column(default="Pending")
    attempts: Mapped[int] = mapped_column(default=0)
    error: Mapped[str] = mapped_column(default="")
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("org_id", "key"),)


class Report(TenantRow, Base):
    __tablename__ = "generated_reports"
    kind: Mapped[str]
    filters: Mapped[dict] = mapped_column(JSON)
    rows: Mapped[list] = mapped_column(JSON)
    metrics: Mapped[dict] = mapped_column(JSON)


class AuditEvent(TenantRow, Base):
    __tablename__ = "audit_events"
    actor: Mapped[str]
    action: Mapped[str]
    entity: Mapped[str]
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


# Persistent identities are deliberately separate from legacy/demo business actors.
# Approval foreign keys continue to reference users.id unchanged.
class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(128), unique=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    job_title: Mapped[str] = mapped_column(String(100), default="")
    phone: Mapped[str] = mapped_column(String(30), default="")
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Kolkata")
    language: Mapped[str] = mapped_column(String(10), default="en")
    onboarding: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Membership(TenantRow, Base):
    __tablename__ = "organization_memberships"
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    role: Mapped[str] = mapped_column(String(16))
    active: Mapped[bool] = mapped_column(default=True)
    __table_args__ = (
        UniqueConstraint("org_id", "account_id"),
        CheckConstraint(
            "role IN ('owner','admin','manager','analyst','viewer')", name="ck_membership_role"
        ),
    )


class AccountSession(Base):
    __tablename__ = "account_sessions"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    org_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    provider_tokens: Mapped[str]  # Authenticated encryption; never serialized to clients.
    recovery: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Invitation(TenantRow, Base):
    __tablename__ = "organization_invitations"
    email: Mapped[str] = mapped_column(String(254))
    role: Mapped[str] = mapped_column(String(16))
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    delivery: Mapped[str] = mapped_column(String(24), default="not_delivered")
    invited_by: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("org_id", "email"),
        CheckConstraint(
            "role IN ('admin','manager','analyst','viewer')", name="ck_invitation_role"
        ),
        CheckConstraint(
            "status IN ('pending','accepted','rejected','expired','revoked')",
            name="ck_invitation_status",
        ),
    )


class AuthenticationEvent(Base):
    __tablename__ = "authentication_audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), index=True)
    action: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class IdentityChallenge(Base):
    __tablename__ = "identity_challenges"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    verifier: Mapped[str]
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    __table_args__ = (CheckConstraint("kind IN ('signup','recovery')", name="ck_challenge_kind"),)


class OAuthChallenge(Base):
    __tablename__ = "oauth_challenges"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    verifier: Mapped[str]
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    @property
    def kind(self):
        return "google"

    @property
    def email(self):
        return None
