"""v14 lead activities refactor + new tables

Revision ID: a3f1e2d4c5b6
Revises: b1e974ca9835
Create Date: 2026-10-10 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a3f1e2d4c5b6'
down_revision: Union[str, None] = 'b1e974ca9835'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # lead_activities：废除 phone_count（+1/+2/+3 累计），改 result 联系结果
    op.drop_constraint(
        'ck_lead_activities_phone_count', 'lead_activities', type_='check'
    )
    op.drop_column('lead_activities', 'phone_count')
    op.add_column(
        'lead_activities', sa.Column('result', sa.String(length=32), nullable=True)
    )

    # lead_parse_records：AI 智能新增解析记录
    op.create_table(
        'lead_parse_records',
        sa.Column('lead_id', sa.UUID(), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column(
            'parsed_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_lead_parse_records_lead_id'),
        'lead_parse_records',
        ['lead_id'],
        unique=False,
    )

    # lead_event_revisions：联系事件修正历史
    op.create_table(
        'lead_event_revisions',
        sa.Column('activity_id', sa.UUID(), nullable=False),
        sa.Column(
            'before_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            'after_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column('reason', sa.String(length=255), nullable=False),
        sa.Column('revised_by', sa.UUID(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['activity_id'], ['lead_activities.id'], ),
        sa.ForeignKeyConstraint(['revised_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_lead_event_revisions_activity_id'),
        'lead_event_revisions',
        ['activity_id'],
        unique=False,
    )

    # app_settings：键值配置（AI 服务等）
    op.create_table(
        'app_settings',
        sa.Column('key', sa.String(length=128), nullable=False),
        sa.Column(
            'value', postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_app_settings_key'), 'app_settings', ['key'], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_app_settings_key'), table_name='app_settings')
    op.drop_table('app_settings')

    op.drop_index(
        op.f('ix_lead_event_revisions_activity_id'),
        table_name='lead_event_revisions',
    )
    op.drop_table('lead_event_revisions')

    op.drop_index(
        op.f('ix_lead_parse_records_lead_id'), table_name='lead_parse_records'
    )
    op.drop_table('lead_parse_records')

    op.drop_column('lead_activities', 'result')
    op.add_column(
        'lead_activities', sa.Column('phone_count', sa.Integer(), nullable=True)
    )
    op.create_check_constraint(
        'ck_lead_activities_phone_count',
        'lead_activities',
        "(kind = 'phone' AND phone_count IN (1, 2, 3)) OR "
        "(kind IN ('wechat', 'note') AND phone_count IS NULL)",
    )
