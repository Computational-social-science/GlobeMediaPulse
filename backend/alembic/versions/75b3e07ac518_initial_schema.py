"""Initial schema

Revision ID: 75b3e07ac518
Revises: 
Create Date: 2026-01-24 06:53:56.182004

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '75b3e07ac518'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    to_drop = [
        op.f("idx_country"),
        op.f("idx_error_events_compound"),
        op.f("idx_error_events_country"),
        op.f("idx_error_events_timestamp"),
        op.f("idx_timestamp"),
        op.f("idx_timestamp_country"),
        op.f("idx_word"),
        op.f("idx_news_articles_published"),
    ]
    for idx in to_drop:
        op.execute(f'DROP INDEX IF EXISTS "{idx}"')

    op.execute('CREATE INDEX IF NOT EXISTS "ix_error_events_country_code" ON error_events (country_code)')
    op.execute('CREATE INDEX IF NOT EXISTS "ix_error_events_id" ON error_events (id)')
    op.execute('CREATE INDEX IF NOT EXISTS "ix_error_events_timestamp" ON error_events (timestamp)')
    op.execute('CREATE INDEX IF NOT EXISTS "ix_error_events_word" ON error_events (word)')
    op.execute('CREATE INDEX IF NOT EXISTS "ix_fetch_logs_id" ON fetch_logs (id)')
    op.execute('CREATE INDEX IF NOT EXISTS "ix_news_articles_id" ON news_articles (id)')
    op.execute('CREATE INDEX IF NOT EXISTS "ix_news_articles_published_at" ON news_articles (published_at)')
    op.execute('CREATE INDEX IF NOT EXISTS "ix_skipped_events_id" ON skipped_events (id)')


def downgrade() -> None:
    """Downgrade schema."""
    to_drop = [
        "ix_skipped_events_id",
        "ix_news_articles_published_at",
        "ix_news_articles_id",
        "ix_fetch_logs_id",
        "ix_error_events_word",
        "ix_error_events_timestamp",
        "ix_error_events_id",
        "ix_error_events_country_code",
    ]
    for idx in to_drop:
        op.execute(f'DROP INDEX IF EXISTS "{idx}"')

    op.execute(f'CREATE INDEX IF NOT EXISTS "{op.f("idx_news_articles_published")}" ON news_articles (published_at)')
    op.execute(f'CREATE INDEX IF NOT EXISTS "{op.f("idx_word")}" ON error_events (word)')
    op.execute(f'CREATE INDEX IF NOT EXISTS "{op.f("idx_timestamp_country")}" ON error_events (timestamp, country_code)')
    op.execute(f'CREATE INDEX IF NOT EXISTS "{op.f("idx_timestamp")}" ON error_events (timestamp)')
    op.execute(f'CREATE INDEX IF NOT EXISTS "{op.f("idx_error_events_timestamp")}" ON error_events (timestamp)')
    op.execute(f'CREATE INDEX IF NOT EXISTS "{op.f("idx_error_events_country")}" ON error_events (country_code)')
    op.execute(f'CREATE INDEX IF NOT EXISTS "{op.f("idx_error_events_compound")}" ON error_events (timestamp, country_code)')
    op.execute(f'CREATE INDEX IF NOT EXISTS "{op.f("idx_country")}" ON error_events (country_code)')
