from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "009_alter_config_to_json"
down_revision: Union[str, None] = "008_create_user_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Alter config column from TEXT to JSON
    # Using USING clause to convert existing TEXT data to JSON
    op.execute(
        sa.text(
            """
            ALTER TABLE jobs 
            ALTER COLUMN config TYPE JSON 
            USING CASE 
                WHEN config IS NULL THEN NULL 
                WHEN config = '' THEN NULL
                ELSE config::JSON 
            END
            """
        )
    )


def downgrade() -> None:
    # Revert JSON column back to TEXT
    op.execute(
        sa.text(
            """
            ALTER TABLE jobs 
            ALTER COLUMN config TYPE TEXT 
            USING CASE 
                WHEN config IS NULL THEN NULL 
                ELSE config::TEXT 
            END
            """
        )
    )
