"""add escalations table

Revision ID: 001_escalations
Revises: 
Create Date: 2026-01-27 12:00:00.000000

"""
# pylint: disable=no-member
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '001_escalations'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "escalations" not in inspector.get_table_names():
        op.create_table(
            "escalations",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("room_number", sa.String(), nullable=True),
            sa.Column("guest_name", sa.String(), nullable=True),
            sa.Column("issue", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("claimed_by", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    index_name = op.f("ix_escalations_room_number")
    existing_indexes = {idx.get("name") for idx in inspector.get_indexes("escalations")}
    if index_name not in existing_indexes:
        op.create_index(index_name, "escalations", ["room_number"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "escalations" not in inspector.get_table_names():
        return

    index_name = op.f("ix_escalations_room_number")
    existing_indexes = {idx.get("name") for idx in inspector.get_indexes("escalations")}
    if index_name in existing_indexes:
        op.drop_index(index_name, table_name="escalations")
    op.drop_table("escalations")
