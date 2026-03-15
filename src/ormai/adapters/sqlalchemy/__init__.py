"""
SQLAlchemy Adapter for OrmAI.

Provides integration with SQLAlchemy 2.0+ for both sync and async operations.
"""

from ormai.adapters.sqlalchemy.adapter import SQLAlchemyAdapter
from ormai.adapters.sqlalchemy.compiler import SQLAlchemyCompiler
from ormai.adapters.sqlalchemy.introspection import SQLAlchemyIntrospector
from ormai.adapters.sqlalchemy.session import SessionManager

__all__ = [
    "SQLAlchemyAdapter",
    "SQLAlchemyIntrospector",
    "SQLAlchemyCompiler",
    "SessionManager",
]
