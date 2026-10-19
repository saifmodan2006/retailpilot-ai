"""Explicit demo tenant boundary; preserve known fictional local demo sessions."""

from alembic import op
import sqlalchemy as sa

revision = "b7c2_public_demo_boundary"
down_revision = "ae43cecefcec"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "organizations",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        sa.text("UPDATE organizations SET is_demo = true WHERE name = 'Threadline Retail · Demo'")
    )


def downgrade():
    with op.batch_alter_table("organizations") as batch:
        batch.drop_column("is_demo")
