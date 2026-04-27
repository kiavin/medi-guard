"""update consultation status to ongoing

Revision ID: 3e4e44f32b0e
Revises: 5e6206cbbbbe
Create Date: 2026-04-07 09:32:28.829215

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3e4e44f32b0e'
down_revision: Union[str, None] = '5e6206cbbbbe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
