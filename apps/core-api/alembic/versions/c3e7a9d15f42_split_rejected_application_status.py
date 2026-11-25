"""Split the rejected application status into rejected_low_score and rejected_screening."""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "c3e7a9d15f42"
down_revision: Union[str, Sequence[str], None] = "b7d4e1f20c93"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_KEPT = "'applied', 'interview_scheduled', 'interview_completed', 'shortlist_for_l1'"

# Every column typed application_status: (table, column).
_COLUMNS = (
    ("applications", "status"),
    ("application_timeline_events", "from_status"),
    ("application_timeline_events", "to_status"),
)


def _retype(new_labels: str, mapping: str) -> None:
    """Rebuild application_status with new labels, converting each column.

    Postgres cannot drop an enum label, so the type is recreated and every
    column is cast across with ``mapping`` (a CASE over ``{col}::text``).
    """
    op.execute("ALTER TYPE application_status RENAME TO application_status_old")
    op.execute(f"CREATE TYPE application_status AS ENUM ({new_labels})")
    op.execute("ALTER TABLE applications ALTER COLUMN status DROP DEFAULT")
    for table, column in _COLUMNS:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE application_status "
            f"USING ({mapping.format(col=column)})::application_status"
        )
    op.execute("ALTER TABLE applications ALTER COLUMN status SET DEFAULT 'applied'")
    op.execute("DROP TYPE application_status_old")


def upgrade() -> None:
    # Until now an application could only be rejected before screening, so
    # every existing rejection was made on the job analysis score.
    _retype(
        f"{_KEPT}, 'rejected_low_score', 'rejected_screening'",
        "CASE WHEN {col}::text = 'rejected' THEN 'rejected_low_score' ELSE {col}::text END",
    )


def downgrade() -> None:
    # Lossy: both kinds become 'rejected', so upgrading again turns every
    # rejection into rejected_low_score.
    _retype(
        f"{_KEPT}, 'rejected'",
        "CASE WHEN {col}::text IN ('rejected_low_score', 'rejected_screening') "
        "THEN 'rejected' ELSE {col}::text END",
    )
