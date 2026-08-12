"""
Database Session Management

Configures SQLAlchemy engine and session factory for Azure SQL and other databases.
Provides context managers for safe database operations.
"""

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from cryptoquant.config.settings import get_settings

logger = logging.getLogger(__name__)

# Global engine instance
_engine: Engine | None = None
_SessionFactory: sessionmaker | None = None


def get_engine(echo: bool = False) -> Engine:
    """
    Get or create SQLAlchemy engine.

    Args:
        echo: If True, log all SQL statements

    Returns:
        SQLAlchemy Engine instance

    Example:
        >>> from cryptoquant.database.session import get_engine
        >>> engine = get_engine()
        >>> print(engine.url)
    """
    global _engine

    if _engine is None:
        settings = get_settings()

        # Configure connection pooling for production use
        _engine = create_engine(
            settings.database_url,
            echo=echo,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,  # Verify connections before using
            pool_recycle=3600,  # Recycle connections after 1 hour
        )

        logger.info(f"Database engine created: {_engine.url.database}")

        # Set up event listeners for Azure SQL if needed
        if "mssql" in str(_engine.url):
            _setup_azure_sql_events(_engine)

    return _engine


def _setup_azure_sql_events(engine: Engine) -> None:
    """Set up Azure SQL specific event listeners."""

    @event.listens_for(engine, "connect")
    def set_isolation_level(dbapi_conn, connection_record):  # type: ignore
        """Set isolation level for Azure SQL connections."""
        cursor = dbapi_conn.cursor()
        cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
        cursor.close()

    logger.info("Azure SQL event listeners configured")


def get_session_factory() -> sessionmaker:
    """
    Get or create session factory.

    Returns:
        SQLAlchemy sessionmaker

    Example:
        >>> from cryptoquant.database.session import get_session_factory
        >>> SessionFactory = get_session_factory()
        >>> session = SessionFactory()
    """
    global _SessionFactory

    if _SessionFactory is None:
        engine = get_engine()
        _SessionFactory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        logger.info("Session factory created")

    return _SessionFactory


def get_session() -> Session:
    """
    Get a new database session.

    Returns:
        SQLAlchemy Session

    Example:
        >>> from cryptoquant.database.session import get_session
        >>> session = get_session()
        >>> try:
        ...     # Perform database operations
        ...     session.commit()
        ... finally:
        ...     session.close()
    """
    SessionFactory = get_session_factory()
    return SessionFactory()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    Provide a transactional scope for database operations.

    Automatically commits on success and rolls back on exception.

    Yields:
        SQLAlchemy Session

    Example:
        >>> from cryptoquant.database.session import session_scope
        >>> from cryptoquant.database.models import Asset
        >>>
        >>> with session_scope() as session:
        ...     asset = Asset(symbol="BTC", name="Bitcoin")
        ...     session.add(asset)
        ...     # Automatically committed on success
    """
    session = get_session()
    try:
        yield session
        session.commit()
        logger.debug("Database transaction committed")
    except Exception as e:
        session.rollback()
        logger.error(f"Database transaction rolled back: {e}")
        raise
    finally:
        session.close()


def init_database() -> None:
    """
    Initialize database schema.

    Creates all tables defined in models. Use Alembic migrations
    for production deployments.

    Example:
        >>> from cryptoquant.database.session import init_database
        >>> init_database()
    """
    from cryptoquant.database.models import Base

    engine = get_engine()
    Base.metadata.create_all(engine)
    logger.info("Database schema initialized")


def drop_database() -> None:
    """
    Drop all database tables.

    WARNING: This will delete all data. Use only in development.

    Example:
        >>> from cryptoquant.database.session import drop_database
        >>> drop_database()  # Only in development!
    """
    from cryptoquant.database.models import Base

    settings = get_settings()
    if settings.is_production:
        raise RuntimeError("Cannot drop database in production")

    engine = get_engine()
    Base.metadata.drop_all(engine)
    logger.warning("All database tables dropped")
