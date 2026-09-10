"""Add in_progress to interview_status enum."""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "e5d2b8a41f36"
down_revision: Union[str, Sequence[str], None] = "c9f3a1e82d04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE interview_status ADD VALUE IF NOT EXISTS 'in_progress' AFTER 'rescheduled'"
    )


def downgrade() -> None:
    # Postgres cannot drop a single enum label; rebuild the type without it.
    op.execute("ALTER TYPE interview_status RENAME TO interview_status_old")
    op.execute(
        "CREATE TYPE interview_status AS ENUM "
        "('scheduled', 'rescheduled', 'completed', 'no_show', 'cancelled', 'failed')"
    )
    op.execute(
        "ALTER TABLE interview_session "
        "ALTER COLUMN status TYPE interview_status "
        "USING (CASE WHEN status::text = 'in_progress' THEN 'scheduled' ELSE status::text END)"
        "::interview_status"
    )
    op.execute("DROP TYPE interview_status_old")
