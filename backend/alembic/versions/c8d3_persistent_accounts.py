"""Add persistent accounts without altering any existing business table or identifier.

Forward only. Recovery uses a verified pre-release checkpoint and the previous
application revision; destructive downgrade is intentionally prohibited.
"""

from alembic import op
import sqlalchemy as sa

revision = "c8d3_persistent_accounts"
down_revision = "b7c2_public_demo_boundary"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider_id", sa.String(128), nullable=False, unique=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("job_title", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("timezone", sa.String(80), nullable=False),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("onboarding", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deletion_requested_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "organization_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("org_id", "account_id"),
        sa.CheckConstraint(
            "role IN ('owner','admin','manager','analyst','viewer')", name="ck_membership_role"
        ),
    )
    for column in ("org_id", "account_id"):
        op.create_index(
            f"ix_organization_memberships_{column}", "organization_memberships", [column]
        )
    op.create_table(
        "account_sessions",
        sa.Column("digest", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id")),
        sa.Column("provider_tokens", sa.String(), nullable=False),
        sa.Column("recovery", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("account_id", "expires_at"):
        op.create_index(f"ix_account_sessions_{column}", "account_sessions", [column])
    op.create_table(
        "organization_invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("token_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("delivery", sa.String(24), nullable=False),
        sa.Column("invited_by", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("org_id", "email"),
        sa.CheckConstraint(
            "role IN ('admin','manager','analyst','viewer')", name="ck_invitation_role"
        ),
        sa.CheckConstraint(
            "status IN ('pending','accepted','rejected','expired','revoked')",
            name="ck_invitation_status",
        ),
    )
    op.create_index("ix_organization_invitations_org_id", "organization_invitations", ["org_id"])
    op.create_table(
        "authentication_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id")),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("account_id", "created_at"):
        op.create_index(
            f"ix_authentication_audit_events_{column}", "authentication_audit_events", [column]
        )

    op.create_table(
        "identity_challenges",
        sa.Column("digest", sa.String(64), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("verifier", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('signup','recovery')", name="ck_challenge_kind"),
    )
    for column in ("email", "expires_at"):
        op.create_index(f"ix_identity_challenges_{column}", "identity_challenges", [column])


def downgrade():
    raise RuntimeError(
        "Forward-only release: restore a verified checkpoint; never drop account or business records."
    )
