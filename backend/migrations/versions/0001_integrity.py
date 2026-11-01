"""Adopt legacy SQLite tables and add durable integrity records without dropping data."""
from alembic import op
from sqlalchemy import inspect
from backend.app.core.database import Base
import backend.app.models.models  # noqa: F401

revision = '0001_integrity'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Baseline supports both a fresh installation and the existing unversioned schema.
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    inspector = inspect(bind)
    for table in Base.metadata.sorted_tables:
        existing = {col['name'] for col in inspector.get_columns(table.name)}
        for col in table.columns:
            if col.name not in existing:
                op.add_column(table.name, col._copy())


def downgrade():
    raise RuntimeError('Baseline downgrade would delete manuscripts; restore a database backup instead.')
