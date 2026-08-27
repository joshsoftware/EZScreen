"""application source + timeline events

Revision ID: a1c4e8b27d90
Revises: f4c1a7e93b20
Create Date: 2026-08-24 16:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1c4e8b27d90"
down_revision: Union[str, Sequence[str], None] = "f4c1a7e93b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

application_source = postgresql.ENUM(
    "hr_bulk",
    "candidate",
    name="application_source",
    create_type=False,
)
timeline_event_type = postgresql.ENUM(
    "applied",
    "scored",
    "resume_parsed",
    "job_fit",
    "under_hr_review",
    "screening_scheduled",
    "invite_sent",
    "screening_in_progress",
    "screening_completed",
    "analysis_ready",
    "shortlisted_for_l1",
    "rejected",
    "screening_rescheduled",
    "screening_no_show",
    "screening_cancelled",
    "screening_failed",
    name="timeline_event_type",
    create_type=False,
)
timeline_actor_type = postgresql.ENUM(
    "user",
    "system",
    name="timeline_actor_type",
    create_type=False,
)


def upgrade() -> None:
    application_source.create(op.get_bind(), checkfirst=True)
    timeline_event_type.create(op.get_bind(), checkfirst=True)
    timeline_actor_type.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "applications",
        sa.Column(
            "source",
            application_source,
            nullable=False,
            server_default="hr_bulk",
        ),
    )
    op.create_index("ix_applications_source", "applications", ["source"])

    op.create_table(
        "application_timeline_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", timeline_event_type, nullable=False),
        sa.Column(
            "from_status",
            postgresql.ENUM(
                "applied",
                "interview_scheduled",
                "interview_completed",
                "shortlist_for_l1",
                "rejected",
                name="application_status",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "to_status",
            postgresql.ENUM(
                "applied",
                "interview_scheduled",
                "interview_completed",
                "shortlist_for_l1",
                "rejected",
                name="application_status",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "actor_type",
            timeline_actor_type,
            nullable=False,
            server_default="system",
        ),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_application_timeline_events_application_created",
        "application_timeline_events",
        ["application_id", "created_at"],
    )
    op.create_index(
        "ix_application_timeline_events_event_type",
        "application_timeline_events",
        ["event_type"],
    )

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
                'scored',
                NULL,
                a.status,
                'system',
                '{"backfill": true}'::jsonb,
                COALESCE(a.applied_at, a.created_at)
            FROM applications a
            """
        )
    )
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
                'resume_parsed',
                NULL,
                a.status,
                'system',
                '{"backfill": true}'::jsonb,
                COALESCE(a.applied_at, a.created_at)
            FROM applications a
            WHERE a.parsed_resume IS NOT NULL
            """
        )
    )
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
                'job_fit',
                NULL,
                a.status,
                'system',
                '{"backfill": true}'::jsonb,
                a.updated_at
            FROM applications a
            WHERE a.resume_score IS NOT NULL OR a.job_fit_analysis IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_application_timeline_events_event_type",
        table_name="application_timeline_events",
    )
    op.drop_index(
        "ix_application_timeline_events_application_created",
        table_name="application_timeline_events",
    )
    op.drop_table("application_timeline_events")
    op.drop_index("ix_applications_source", table_name="applications")
    op.drop_column("applications", "source")
    timeline_actor_type.drop(op.get_bind(), checkfirst=True)
    timeline_event_type.drop(op.get_bind(), checkfirst=True)
    application_source.drop(op.get_bind(), checkfirst=True)
