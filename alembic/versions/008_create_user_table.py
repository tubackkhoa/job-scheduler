from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "008_create_user_table"
down_revision: Union[str, None] = "007_add_signal_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS users_id_seq"))
    
    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.Integer(),
            server_default=sa.text("nextval('users_id_seq'::regclass)"),
            nullable=False,
        ),
        sa.Column("username", sa.String(length=150), nullable=False),
        sa.Column("password", sa.String(length=255), nullable=False),
        sa.Column("roles", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    
    op.create_index("ix_users_id", "users", ["id"], unique=False)
    op.create_index("ix_users_username", "users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
    op.execute(sa.text("DROP SEQUENCE IF EXISTS users_id_seq"))
