
"""add rows_removed to datasets

Revision ID: 32f891bd69c0
Revises: f68aab9de02f
"""

from typing import Sequence, Union

# Revision identifiers
revision: str = "32f891bd69c0"
down_revision: Union[str, Sequence[str], None] = "f68aab9de02f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No schema changes are required for the rows_removed property."""
    pass


def downgrade() -> None:
    """No schema changes to reverse."""
    pass
