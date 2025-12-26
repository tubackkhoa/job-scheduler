
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "003_change_active_to_boolean"
down_revision: Union[str, None] = "002_add_session_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def constraint_exists(table_name: str, constraint_name: str) -> bool:
    """Check if a constraint exists in a table."""
    try:
        bind = op.get_bind()
        inspector = inspect(bind)
        constraints = [c["name"] for c in inspector.get_check_constraints(table_name)]
        return constraint_name in constraints
    except Exception:
        return False


def upgrade() -> None:
    if constraint_exists("jobs", "ck_jobs_active_bool"):
        op.drop_constraint("ck_jobs_active_bool", "jobs", type_="check")
    
    # Drop existing default before changing type to avoid casting error
    op.alter_column("jobs", "active", server_default=None)
    
    op.execute(
        sa.text("""
            ALTER TABLE jobs 
            ALTER COLUMN active TYPE boolean 
            USING CASE 
                WHEN active = 1 THEN true 
                WHEN active = 0 THEN false 
                ELSE false 
            END
        """)
    )
    
    # Set default value to true (boolean)
    op.alter_column(
        "jobs",
        "active",
        server_default=sa.text("true"),
        nullable=False,
    )


def downgrade() -> None:
    # Drop existing default before changing type
    op.alter_column("jobs", "active", server_default=None)
    
    # Convert boolean back to integer
    op.execute(
        sa.text("""
            ALTER TABLE jobs 
            ALTER COLUMN active TYPE integer 
            USING CASE 
                WHEN active = true THEN 1 
                WHEN active = false THEN 0 
                ELSE 0 
            END
        """)
    )
    
    # Set default value back to 1 (integer)
    op.alter_column(
        "jobs",
        "active",
        server_default=sa.text("1"),
        nullable=False,
    )
    
    # Re-add the check constraint
    op.create_check_constraint(
        "ck_jobs_active_bool",
        "jobs",
        sa.text("active IN (0,1)"),
    )

