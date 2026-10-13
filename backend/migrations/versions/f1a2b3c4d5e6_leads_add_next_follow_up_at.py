"""leads add next_follow_up_at

Revision ID: f1a2b3c4d5e6
Revises: a3f1e2d4c5b6
Create Date: 2026-10-12

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'a3f1e2d4c5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 下次计划跟进时间（跟进待办依赖的核心字段）
    op.add_column(
        'leads', sa.Column('next_follow_up_at', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('leads', 'next_follow_up_at')
