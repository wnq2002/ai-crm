"""leads external event unique index

Revision ID: 7ad73d5f13fb
Revises: e62b96822f83
Create Date: 2026-10-10 10:19:33.323057

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7ad73d5f13fb'
down_revision: Union[str, None] = 'e62b96822f83'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 渠道作用域唯一：同一来源渠道下，外部事件 ID 唯一（防重复入库）
    op.create_index(
        'uq_leads_external_event',
        'leads',
        ['source_category_id', 'external_source_event_id'],
        unique=True,
        postgresql_where=sa.text('external_source_event_id IS NOT NULL'),
    )


def downgrade() -> None:
    op.drop_index(
        'uq_leads_external_event',
        table_name='leads',
        postgresql_where=sa.text('external_source_event_id IS NOT NULL'),
    )
