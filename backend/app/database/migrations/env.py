
import os
import sys
from logging.config import fileConfig

from dotenv import load_dotenv
from alembic import context
from sqlalchemy import engine_from_config, pool

# Load environment variables before importing application settings.
load_dotenv()

# Ensure the backend directory is available for imports.
sys.path.insert(0, os.getcwd())

from app.core.config import settings
from app.database.base import Base

# Import all models so Alembic can detect their tables and relationships.
from app.models.user import User
from app.models.workspace import Workspace
from app.models.dataset import Dataset
from app.models.etl_log import ETLLog
from app.models.relationship import (
    DatasetRelationship,
    DatasetPrimaryKey,
)
from app.models.knowledge_base import (
    BusinessEntity,
    BusinessMetric,
    BusinessRule,
)
from app.models.query_history import QueryHistory
from app.models.reports import Report


# Alembic configuration
config = context.config

# Use the database URL from application settings, not localhost
# hardcoded in alembic.ini.
database_url = settings.DATABASE_URL

if not database_url:
    raise RuntimeError(
        "DATABASE_URL is missing. Configure it in your environment."
    )

# Escape percent signs for ConfigParser interpolation.
config.set_main_option(
    "sqlalchemy.url",
    database_url.replace("%", "%%"),
)

# Configure logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Register application models with Alembic.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without creating a database connection."""

    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using a live database connection."""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
