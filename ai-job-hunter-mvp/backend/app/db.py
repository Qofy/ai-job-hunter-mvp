"""SQLite files live in application data, never in the source checkout."""
import os
from functools import lru_cache
from pathlib import Path
from threading import RLock
from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

BACKEND = Path(__file__).resolve().parents[1]
REPOSITORY = next((parent for parent in BACKEND.parents if (parent / '.git').exists()), BACKEND.parent)
_lock = RLock()
_migrated: set[str] = set()


def data_directory() -> Path:
    default = Path(os.getenv('LOCALAPPDATA', str(Path.home() / '.local' / 'share'))) / 'JobPilotAI'
    path = Path(os.getenv('JOBPILOT_DATA_DIR', str(default))).expanduser().resolve()
    if path.is_relative_to(REPOSITORY):
        raise RuntimeError('JOBPILOT_DATA_DIR must be outside the source repository.')
    path.mkdir(parents=True, exist_ok=True)
    (path / 'files').mkdir(exist_ok=True)
    return path


@lru_cache(maxsize=16)
def _engine(path: str):
    engine = create_engine(URL.create('sqlite', database=path), connect_args={'check_same_thread': False, 'timeout': 10})

    @event.listens_for(engine, 'connect')
    def configure(connection, _):
        connection.isolation_level = None
        cursor = connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA busy_timeout=10000')
        cursor.close()

    @event.listens_for(engine, 'begin')
    def begin(connection):
        connection.exec_driver_sql('BEGIN')

    return engine


def get_engine():
    return _engine(str(data_directory() / 'jobpilot.sqlite3'))


def initialize():
    from alembic import command
    from alembic.config import Config
    engine = get_engine()
    with _lock:
        key = str(engine.url)
        if key not in _migrated:
            config = Config(str(BACKEND / 'alembic.ini'))
            config.set_main_option('script_location', str(BACKEND / 'migrations'))
            with engine.begin() as connection:
                config.attributes['connection'] = connection
                command.upgrade(config, 'head')
            _migrated.add(key)
    return engine


def get_session():
    with Session(initialize(), expire_on_commit=False) as session:
        yield session
