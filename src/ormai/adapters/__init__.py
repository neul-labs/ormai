"""
OrmAI Adapters Module.

Contains the abstract adapter interface and implementations for various ORMs.
"""

from ormai.adapters.base import CompiledQuery, OrmAdapter

__all__ = [
    "OrmAdapter",
    "CompiledQuery",
]

# Lazy imports for specific adapters to avoid requiring all dependencies
def get_sqlalchemy_adapter():
    """Get the SQLAlchemy adapter class."""
    from ormai.adapters.sqlalchemy import SQLAlchemyAdapter
    return SQLAlchemyAdapter
