"""add events table

Revision ID: bc5180ba6081
Revises: 001_escalations
Create Date: 2026-02-24 00:19:36.374100

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'bc5180ba6081'
down_revision = '001_escalations'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "events" not in inspector.get_table_names():
        op.create_table(
            "events",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("source", sa.String(), nullable=False),
            sa.Column("type", sa.String(), nullable=False),
            sa.Column("severity", sa.String(), nullable=False, server_default=sa.text("'low'")),
            sa.Column("text", sa.Text(), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )

    existing_indexes = {idx.get("name") for idx in inspector.get_indexes("events")}
    if "ix_events_created_at" not in existing_indexes:
        op.create_index("ix_events_created_at", "events", ["created_at"], unique=False)
    if "ix_events_source" not in existing_indexes:
        op.create_index("ix_events_source", "events", ["source"], unique=False)
    if "ix_events_type" not in existing_indexes:
        op.create_index("ix_events_type", "events", ["type"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "events" not in inspector.get_table_names():
        return

    existing_indexes = {idx.get("name") for idx in inspector.get_indexes("events")}
    for name in ("ix_events_created_at", "ix_events_source", "ix_events_type"):
        if name in existing_indexes:
            op.drop_index(name, table_name="events")
    op.drop_table("events")
