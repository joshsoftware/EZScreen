"""Job role intro: a few sentences the AI interviewer reads about the role.

Revision ID: b7d4e1f20c93
Revises: a8f3c2e19d47
Create Date: 2026-11-09 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7d4e1f20c93"
down_revision: Union[str, Sequence[str], None] = "a8f3c2e19d47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("job_descriptions", sa.Column("role_intro", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("job_descriptions", "role_intro")
