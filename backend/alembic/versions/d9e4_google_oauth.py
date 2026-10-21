"""Add bounded Google OAuth PKCE state; preserve existing accounts and retail data."""

from alembic import op
import sqlalchemy as sa

revision = "d9e4_google_oauth"
down_revision = "c8d3_persistent_accounts"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "oauth_challenges",
        sa.Column("digest", sa.String(64), primary_key=True),
        sa.Column("verifier", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_oauth_challenges_expires_at", "oauth_challenges", ["expires_at"])


def downgrade():
    raise RuntimeError("Forward-only release. Restore a verified checkpoint instead.")
