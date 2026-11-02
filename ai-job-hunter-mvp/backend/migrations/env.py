from alembic import context
from app.db import get_engine
from app.models import Base


def run(connection):
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(url='sqlite://', target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
elif context.config.attributes.get('connection') is not None:
    run(context.config.attributes['connection'])
else:
    with get_engine().begin() as connection:
        run(connection)
