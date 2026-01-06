import json
import logging
import os

from contextlib import contextmanager
from typing import Any, Optional
from sqlalchemy import Dialect, create_engine, MetaData, types
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.sql.type_api import _T
from typing_extensions import Self
from peewee_migrate import Router

from app.internal.wrapper import register_connection
from app.config import DATABASE_URL, APP_DIR, DATA_DIR

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class JSONField(types.TypeDecorator):
    """Custom JSON Field for SQLAlchemy."""

    impl = types.Text
    cache_ok = True

    def process_bind_param(
        self, value: Optional[_T], dialect: Dialect
    ) -> Optional[str]:
        return json.dumps(value)

    def process_result_value(
        self, value: Optional[_T], dialect: Dialect
    ) -> Optional[Any]:
        if value is not None:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return []

    def copy(self, **kw) -> Self:
        return JSONField(self.impl.length)

    def db_value(self, value):
        return json.dumps(value)

    def python_value(self, value):
        if value is not None:
            return json.loads(value)


def execute_peewee_migration(DB_URL: str):
    """Execute Peewee migrations before Alembic migrations."""

    try:
        db = register_connection(DB_URL)
        migrate_dir = APP_DIR / "internal" / "migrations"
        router = Router(db, logger=logger, migrate_dir=migrate_dir)

        if os.path.exists(DATA_DIR / "netacad.db"):
            pending_migrations = router.diff
            all_migrations = router.done

            if not pending_migrations or len(pending_migrations) == 0:
                logger.info("No pending Peewee migrations. Skipping....")
                db.close()
            else:
                logger.info(f"Pending Peewee migrations: {pending_migrations}")
                router.run()
                logger.info("Peewee migrations applied successfully.")
                db.close()

        else:
            router.run()
            logger.info("Peewee migrations applied successfully on new database.")
            db.close()
    except Exception as e:
        logger.error(f"Error during Peewee migrations: {e}")
        raise

    finally:
        if db and not db.is_closed():
            db.close()

        assert db.is_closed(), "Database connection should be closed after migrations."


# execute_peewee_migration(DATABASE_URL)
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
)
metadata = MetaData(schema=None)
Base = declarative_base(metadata=metadata)
Session = scoped_session(SessionLocal)


def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


get_db = contextmanager(get_session)
