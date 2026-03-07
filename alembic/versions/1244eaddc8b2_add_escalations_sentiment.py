"""add sentiment column to escalations table

Revision ID: 1244eaddc8b2
Revises: bc5180ba6081
Create Date: 2026-02-24 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "1244eaddc8b2"
down_revision = "bc5180ba6081"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "escalations" not in inspector.get_table_names():
        return

    existing_columns = {col.get("name") for col in inspector.get_columns("escalations")}
    if "sentiment" in existing_columns:
        return

    # Needed by app/db.py Escalation + Retell ingestion ticket creation.
    with op.batch_alter_table("escalations") as batch_op:
        batch_op.add_column(
            sa.Column(
                "sentiment",
                sa.String(),
                nullable=False,
                server_default=sa.text("'Neutral'"),
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "escalations" not in inspector.get_table_names():
        return

    existing_columns = {col.get("name") for col in inspector.get_columns("escalations")}
    if "sentiment" not in existing_columns:
        return

    with op.batch_alter_table("escalations") as batch_op:
        batch_op.drop_column("sentiment")
