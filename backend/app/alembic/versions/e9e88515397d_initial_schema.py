"""initial schema

Revision ID: e9e88515397d
Revises:
Create Date: 2026-01-05 12:44:28.851006

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from app.internal.db import JSONField
from app.alembic.util import get_existing_tables


# revision identifiers, used by Alembic.
revision: str = "e9e88515397d"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    existing_tables = set(get_existing_tables())
    if "auths" not in existing_tables:
        op.create_table(
            "auths",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("email", sa.String(), nullable=False, unique=True),
            sa.Column("password", sa.Text(), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=True),
        )

    if "users" not in existing_tables:
        op.create_table(
            "users",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("name", sa.String(), nullable=True),
            sa.Column("email", sa.String(), nullable=False, unique=True),
            sa.Column("settings", JSONField, nullable=True),
            sa.Column("oauth_sub", sa.Text(), nullable=True, unique=True),
            sa.Column("last_active_at", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.Column("updated_at", sa.BigInteger(), nullable=False),
        )

    if "courses" not in existing_tables:
        op.create_table(
            "courses",
            sa.Column("id", sa.String(length=500), primary_key=True),
            sa.Column("course_id", sa.String(length=500), nullable=False, unique=True),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("url", sa.Text(), nullable=False),
            sa.Column("status", sa.Text(), nullable=True, server_default="active"),
            sa.Column("start_date", sa.Date(), nullable=True),
            sa.Column("end_date", sa.Date(), nullable=True),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.Column("updated_at", sa.BigInteger(), nullable=False),
        )

    if "sync_status" not in existing_tables:
        op.create_table(
            "sync_status",
            sa.Column("id", sa.String(length=500), primary_key=True),
            sa.Column("status", sa.String(length=500), nullable=False),
            sa.Column("started_at", sa.BigInteger(), nullable=True),
            sa.Column("completed_at", sa.BigInteger(), nullable=True),
            sa.Column(
                "total_scraped", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column("new_courses", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "updated_courses", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column(
                "existing_courses", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column(
                "failed_courses", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.Column("updated_at", sa.BigInteger(), nullable=False),
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("sync_status")
    op.drop_table("courses")
    op.drop_table("users")
    op.drop_table("auths")
