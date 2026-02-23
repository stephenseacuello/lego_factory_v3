"""
Database session compatibility shim.

Provides get_session() for code that expects a plain session object
(as opposed to the context-manager-based get_db_session()).
"""
from config.database import get_session_factory


def get_session():
    """Return a new database session. Caller is responsible for closing it."""
    return get_session_factory()()
