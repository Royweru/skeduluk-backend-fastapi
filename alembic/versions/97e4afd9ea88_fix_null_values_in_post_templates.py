"""fix_null_values_in_post_templates

Revision ID: fix_nulls_xxxxx
Revises: <your_previous_revision>
Create Date: 2026-01-12

This migration fixes NULL values in post_templates table that should have defaults
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# At the top of the file
revision = '97e4afd9ea88'
down_revision = '3e5b60f884bc'  # ✅ This is the one!
branch_labels = None
depends_on = None

def upgrade():
    """
    Step 1: Update existing NULL values to their defaults
    Step 2: Add NOT NULL constraints to ensure data integrity
    """
    
    # Fix existing NULL values
    op.execute("""
        UPDATE post_templates 
        SET 
            is_favorite = COALESCE(is_favorite, FALSE),
            is_public = COALESCE(is_public, FALSE),
            is_premium = COALESCE(is_premium, FALSE),
            is_system = COALESCE(is_system, FALSE),
            usage_count = COALESCE(usage_count, 0),
            success_rate = COALESCE(success_rate, 0),
            tone = COALESCE(tone, 'engaging'),
            color_scheme = COALESCE(color_scheme, '#3B82F6'),
            icon = COALESCE(icon, 'sparkles'),
            created_at = COALESCE(created_at, CURRENT_TIMESTAMP),
            updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)
        WHERE 
            is_favorite IS NULL 
            OR is_public IS NULL
            OR is_premium IS NULL
            OR is_system IS NULL
            OR usage_count IS NULL 
            OR success_rate IS NULL
            OR tone IS NULL
            OR color_scheme IS NULL
            OR icon IS NULL
            OR created_at IS NULL 
            OR updated_at IS NULL
    """)
    
    # Now make columns NOT NULL with server defaults
    # Boolean columns
    op.alter_column('post_templates', 'is_favorite',
                    existing_type=sa.Boolean(),
                    nullable=False,
                    server_default=sa.text('FALSE'))
    
    op.alter_column('post_templates', 'is_public',
                    existing_type=sa.Boolean(),
                    nullable=False,
                    server_default=sa.text('FALSE'))
    
    op.alter_column('post_templates', 'is_premium',
                    existing_type=sa.Boolean(),
                    nullable=False,
                    server_default=sa.text('FALSE'))
    
    op.alter_column('post_templates', 'is_system',
                    existing_type=sa.Boolean(),
                    nullable=False,
                    server_default=sa.text('FALSE'))
    
    # Integer columns
    op.alter_column('post_templates', 'usage_count',
                    existing_type=sa.Integer(),
                    nullable=False,
                    server_default=sa.text('0'))
    
    op.alter_column('post_templates', 'success_rate',
                    existing_type=sa.Integer(),
                    nullable=False,
                    server_default=sa.text('0'))
    
    # String columns
    op.alter_column('post_templates', 'tone',
                    existing_type=sa.String(),
                    nullable=False,
                    server_default=sa.text("'engaging'"))
    
    op.alter_column('post_templates', 'color_scheme',
                    existing_type=sa.String(),
                    nullable=False,
                    server_default=sa.text("'#3B82F6'"))
    
    op.alter_column('post_templates', 'icon',
                    existing_type=sa.String(),
                    nullable=False,
                    server_default=sa.text("'sparkles'"))
    
    # DateTime columns
    op.alter_column('post_templates', 'created_at',
                    existing_type=sa.DateTime(),
                    nullable=False,
                    server_default=sa.text('CURRENT_TIMESTAMP'))
    
    op.alter_column('post_templates', 'updated_at',
                    existing_type=sa.DateTime(),
                    nullable=False,
                    server_default=sa.text('CURRENT_TIMESTAMP'))


def downgrade():
    """
    Revert columns back to nullable (if needed for rollback)
    """
    
    # Remove NOT NULL constraints
    op.alter_column('post_templates', 'is_favorite',
                    existing_type=sa.Boolean(),
                    nullable=True)
    
    op.alter_column('post_templates', 'is_public',
                    existing_type=sa.Boolean(),
                    nullable=True)
    
    op.alter_column('post_templates', 'is_premium',
                    existing_type=sa.Boolean(),
                    nullable=True)
    
    op.alter_column('post_templates', 'is_system',
                    existing_type=sa.Boolean(),
                    nullable=True)
    
    op.alter_column('post_templates', 'usage_count',
                    existing_type=sa.Integer(),
                    nullable=True)
    
    op.alter_column('post_templates', 'success_rate',
                    existing_type=sa.Integer(),
                    nullable=True)
    
    op.alter_column('post_templates', 'tone',
                    existing_type=sa.String(),
                    nullable=True)
    
    op.alter_column('post_templates', 'color_scheme',
                    existing_type=sa.String(),
                    nullable=True)
    
    op.alter_column('post_templates', 'icon',
                    existing_type=sa.String(),
                    nullable=True)
    
    op.alter_column('post_templates', 'created_at',
                    existing_type=sa.DateTime(),
                    nullable=True)
    
    op.alter_column('post_templates', 'updated_at',
                    existing_type=sa.DateTime(),
                    nullable=True)