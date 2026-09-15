"""create video_uploads table

Revision ID: 7eade38fd766
Revises: 70e507e0b2b1
Create Date: 2026-09-14 08:40:33.557016

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7eade38fd766'
down_revision: Union[str, Sequence[str], None] = '70e507e0b2b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'video_uploads',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('video_id', sa.Integer(), nullable=False),
        sa.Column('total_size', sa.Integer(), nullable=False),
        sa.Column('storage_path', sa.String(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('video_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('video_uploads')
