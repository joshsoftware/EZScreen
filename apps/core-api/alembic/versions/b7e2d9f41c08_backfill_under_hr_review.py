"""Backfill under_hr_review after job_fit.

Revision ID: b7e2d9f41c08
Revises: a1c4e8b27d90
Create Date: 2026-08-26

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7e2d9f41c08"
down_revision: Union[str, Sequence[str], None] = "a1c4e8b27d90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Applications with job fit automatically enter HR review.
    op.execute(
        sa.text(
            """
            INSERT INTO application_timeline_events (
                id, application_id, event_type, from_status, to_status,
                actor_type, metadata, created_at
            )
            SELECT
                gen_random_uuid(),
                a.id,
                'under_hr_review',
                a.status,
                a.status,
                'system',
                '{"auto": true, "after": "job_fit", "backfill": true}'::jsonb,
                COALESCE(
                    (
                        SELECT MAX(e.created_at)
                        FROM application_timeline_events e
                        WHERE e.application_id = a.id
                          AND e.event_type = 'job_fit'
                    ),
                    a.updated_at,
                    a.created_at
                )
            FROM applications a
            WHERE a.status = 'applied'
              AND (
                    a.resume_score IS NOT NULL
                    OR a.job_fit_analysis IS NOT NULL
                    OR EXISTS (
                        SELECT 1
                        FROM application_timeline_events jf
                        WHERE jf.application_id = a.id
                          AND jf.event_type = 'job_fit'
                    )
              )
              AND NOT EXISTS (
                    SELECT 1
                    FROM application_timeline_events e
                    WHERE e.application_id = a.id
                      AND e.event_type IN (
                        'under_hr_review',
                        'rejected',
                        'shortlisted_for_l1'
                      )
              )
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM application_timeline_events
            WHERE event_type = 'under_hr_review'
              AND actor_type = 'system'
              AND metadata @> '{"auto": true, "after": "job_fit"}'::jsonb
            """
        )
    )
