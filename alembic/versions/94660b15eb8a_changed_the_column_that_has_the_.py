"""Changed the column that has the enhanced platform content to be of JSON

Revision ID: 94660b15eb8a
Revises: a1f2ddd9f649
Create Date: 2025-10-25 15:53:30.325886

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '94660b15eb8a'
down_revision: Union[str, Sequence[str], None] = 'a1f2ddd9f649'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Convert TEXT to JSON with explicit casting
    op.execute("""
        ALTER TABLE posts 
        ALTER COLUMN platform_specific_content 
        TYPE JSON 
        USING CASE 
            WHEN platform_specific_content IS NULL THEN NULL
            WHEN platform_specific_content = '' THEN NULL
            ELSE platform_specific_content::json
        END
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Convert JSON back to TEXT
    op.execute("""
        ALTER TABLE posts 
        ALTER COLUMN platform_specific_content 
        TYPE TEXT 
        USING platform_specific_content::text
    """)