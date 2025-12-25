"""add session_id to jobs

Revision ID: 002_add_session_id
Revises: 001_initial
Create Date: 2025-12-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "002_add_session_id"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    try:
        bind = op.get_bind()
        inspector = inspect(bind)
        columns = [col["name"] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        # If inspection fails, assume column doesn't exist
        return False


def upgrade() -> None:
    if not column_exists("jobs", "session_id"):
        op.add_column(
            "jobs",
            sa.Column("session_id", sa.Integer(), nullable=False, server_default=sa.text("1")),
        )
        # Remove server_default after adding for clean schema
        op.alter_column("jobs", "session_id", server_default=None)


def downgrade() -> None:
   
    if column_exists("jobs", "session_id"):
        op.drop_column("jobs", "session_id")

