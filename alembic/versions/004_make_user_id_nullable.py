
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "004_make_user_id_nullable"
down_revision: Union[str, None] = "003_change_active_to_boolean"
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
        return False


def upgrade() -> None:
    # Check if user_id column exists and make it nullable
    if column_exists("jobs", "user_id"):
        op.alter_column(
            "jobs",
            "user_id",
            existing_type=sa.Integer(),
            nullable=True,
        )


def downgrade() -> None:
    if column_exists("jobs", "user_id"):
        op.execute(
            sa.text("UPDATE jobs SET user_id = 1 WHERE user_id IS NULL")
        )
        op.alter_column(
            "jobs",
            "user_id",
            existing_type=sa.Integer(),
            nullable=False,
        )

