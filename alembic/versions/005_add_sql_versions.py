from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "005_add_sql_versions"
down_revision: Union[str, None] = "004_make_user_id_nullable"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create sequence for sql_versions
    op.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS sql_versions_id_seq"))

    # Create sql_versions table
    op.create_table(
        "sql_versions",
        sa.Column(
            "id",
            sa.Integer(),
            server_default=sa.text("nextval('sql_versions_id_seq'::regclass)"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sql_query", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("tags", sa.Text(), nullable=True),  # JSON stored as text
        sa.PrimaryKeyConstraint("id"),
    )

    # Create index on session_id for faster queries
    op.create_index(
        "ix_sql_versions_name",
        "sql_versions",
        ["name"],
    )


def downgrade() -> None:
    op.drop_index("ix_sql_versions_name", table_name="sql_versions")
    op.drop_table("sql_versions")
    op.execute(sa.text("DROP SEQUENCE IF EXISTS sql_versions_id_seq"))
