"""adicionar created at para users

Revision ID: b571b1984dfc
Revises: 44916e01a7ed
Create Date: 2026-11-12 20:39:40.366289

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b571b1984dfc"
down_revision: Union[str, None] = "44916e01a7ed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "created_at")
