"""Allow fractional overall experience years (one decimal place).

Revision ID: a8f3c2e19d47
Revises: e5d2b8a41f36
Create Date: 2026-09-23 13:40:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a8f3c2e19d47"
down_revision: Union[str, Sequence[str], None] = "e5d2b8a41f36"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "job_descriptions",
        "experience_min",
        existing_type=sa.Integer(),
        type_=sa.Float(),
        existing_nullable=True,
        postgresql_using="experience_min::double precision",
    )
    op.alter_column(
        "job_descriptions",
        "experience_max",
        existing_type=sa.Integer(),
        type_=sa.Float(),
        existing_nullable=True,
        postgresql_using="experience_max::double precision",
    )


def downgrade() -> None:
    op.alter_column(
        "job_descriptions",
        "experience_min",
        existing_type=sa.Float(),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="ROUND(experience_min)::integer",
    )
    op.alter_column(
        "job_descriptions",
        "experience_max",
        existing_type=sa.Float(),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="ROUND(experience_max)::integer",
    )
