from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006_add_value_versions"
down_revision: Union[str, None] = "005_add_sql_versions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS value_versions_id_seq"))

    op.create_table(
        "value_versions",
        sa.Column(
            "id",
            sa.Integer(),
            server_default=sa.text("nextval('value_versions_id_seq'::regclass)"),
            nullable=False,
        ),
        sa.Column("field_id", sa.String(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("value", sa.Text(), nullable=False),
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
        sa.Column("tags", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_value_versions_field_id", "value_versions", ["field_id"])


def downgrade() -> None:
    op.drop_index("ix_value_versions_field_id", table_name="value_versions")
    op.drop_table("value_versions")
    op.execute(sa.text("DROP SEQUENCE IF EXISTS value_versions_id_seq"))
