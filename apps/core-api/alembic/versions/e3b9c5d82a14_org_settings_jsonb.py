"""organization settings jsonb for fit labels

Revision ID: e3b9c5d82a14
Revises: d2a8f4c91b07
Create Date: 2026-08-20 14:20:00.000000

"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e3b9c5d82a14"
down_revision: Union[str, Sequence[str], None] = "d2a8f4c91b07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULT_SETTINGS = {
    "fit_labels": [
        {"id": "strong", "name": "Strong", "min_score": 8, "max_score": 10},
        {"id": "moderate", "name": "Moderate", "min_score": 6, "max_score": 7.9},
        {"id": "weak", "name": "Weak", "min_score": 0, "max_score": 5.9},
    ],
}


def upgrade() -> None:
    default_sql = sa.text(f"'{json.dumps(_DEFAULT_SETTINGS)}'::jsonb")
    op.add_column(
        "organizations",
        sa.Column(
            "settings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=default_sql,
        ),
    )


def downgrade() -> None:
    op.drop_column("organizations", "settings")
