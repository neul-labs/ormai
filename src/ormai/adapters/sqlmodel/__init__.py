"""
SQLModel adapter for OrmAI.

SQLModel is built on SQLAlchemy, so this adapter wraps the SQLAlchemy adapter
with SQLModel-specific conveniences.

Note: Requires sqlmodel to be installed.
Install with: pip install sqlmodel
"""

try:
    from ormai.adapters.sqlmodel.adapter import SQLModelAdapter

    __all__ = [
        "SQLModelAdapter",
    ]
except ImportError:
    # SQLModel not installed
    __all__ = []
