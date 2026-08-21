"""job skills jsonb

Revision ID: d2a8f4c91b07
Revises: c478691b4383
Create Date: 2026-08-20 12:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d2a8f4c91b07"
down_revision: Union[str, Sequence[str], None] = "c478691b4383"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE job_descriptions
        ALTER COLUMN skills TYPE jsonb
        USING CASE
            WHEN skills IS NULL OR btrim(skills) = '' THEN NULL
            WHEN left(btrim(skills), 1) IN ('{', '[') THEN skills::jsonb
            ELSE NULL
        END
        """
    )


def downgrade() -> None:
    op.alter_column(
        "job_descriptions",
        "skills",
        type_=postgresql.TEXT(),
        postgresql_using="skills::text",
        existing_nullable=True,
    )
