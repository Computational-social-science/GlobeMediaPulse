"""Migration smoke table

Revision ID: 1a9b6d4c2f10
Revises: 75b3e07ac518
Create Date: 2026-02-04

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1a9b6d4c2f10"
down_revision: Union[str, Sequence[str], None] = "75b3e07ac518"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "__migration_smoke__",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("__migration_smoke__")

