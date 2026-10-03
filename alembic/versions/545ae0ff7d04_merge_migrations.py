"""Merge migrations

Revision ID: 545ae0ff7d04
Revises: 5136d752deb7, b83d10df8605
Create Date: 2026-10-03 00:39:26.725006

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
import geoalchemy2



# revision identifiers, used by Alembic.
revision: str = '545ae0ff7d04'
down_revision: Union[str, None] = ('5136d752deb7', 'b83d10df8605')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
