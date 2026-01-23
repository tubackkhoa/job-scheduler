from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007_add_signal_messages"
down_revision: Union[str, None] = "006_add_value_versions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS signal_messages_id_seq"))

    op.create_table(
        "signal_messages",
        sa.Column(
            "id",
            sa.Integer(),
            server_default=sa.text("nextval('signal_messages_id_seq'::regclass)"),
            nullable=False,
        ),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("model_key", sa.Text(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            default=sa.func.now(),
        ),
        sa.Column(
            "captured_at",
            sa.DateTime(),
            default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("idx_signal_messages_job_id", "signal_messages", ["job_id"])
    op.create_index("idx_signal_messages_model_key", "signal_messages", ["model_key"])


def downgrade() -> None:
    op.drop_index("idx_signal_messages_model_key", table_name="signal_messages")
    op.drop_index("idx_signal_messages_job_id", table_name="signal_messages")
    op.drop_table("signal_messages")
    op.execute(sa.text("DROP SEQUENCE IF EXISTS signal_messages_id_seq"))
