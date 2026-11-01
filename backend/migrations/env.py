from alembic import context
from sqlalchemy import engine_from_config, pool
from backend.app.core.database import Base
import backend.app.models.models  # noqa: F401


def run(connection):
    context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(url=context.config.get_main_option('sqlalchemy.url'), target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
elif context.config.attributes.get('connection') is not None:
    run(context.config.attributes['connection'])
else:
    engine = engine_from_config(context.config.get_section(context.config.config_ini_section), prefix='sqlalchemy.', poolclass=pool.NullPool)
    with engine.connect() as connection:
        run(connection)
