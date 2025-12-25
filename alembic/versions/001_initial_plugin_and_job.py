from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Explicitly create sequences for PostgreSQL
    op.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS plugins_id_seq"))
    op.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS jobs_id_seq"))

    # Create plugins table
    op.create_table(
        "plugins",
        sa.Column(
            "id",
            sa.Integer(),
            server_default=sa.text("nextval('plugins_id_seq'::regclass)"),
            nullable=False,
        ),
        sa.Column("package", sa.Text(), nullable=False),
        sa.Column("interval", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("package"),
        sa.CheckConstraint("interval > 0", name="ck_plugins_interval_positive"),
    )

    # Create jobs table
    op.create_table(
        "jobs",
        sa.Column(
            "id",
            sa.Integer(),
            server_default=sa.text("nextval('jobs_id_seq'::regclass)"),
            nullable=False,
        ),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("plugin_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("config", sa.Text(), nullable=True),
        sa.Column("active", sa.Integer(), nullable=False, server_default=text("1")),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("active IN (0,1)", name="ck_jobs_active_bool"),
    )


def downgrade() -> None:
    op.drop_table("jobs")
    op.drop_table("plugins")
    op.execute(sa.text("DROP SEQUENCE IF EXISTS jobs_id_seq"))
    op.execute(sa.text("DROP SEQUENCE IF EXISTS plugins_id_seq"))
