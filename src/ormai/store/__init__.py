"""
OrmAI Store Module.

Provides audit logging infrastructure and optional conversation history.
"""

from ormai.store.base import AuditStore
from ormai.store.jsonl import JsonlAuditStore
from ormai.store.middleware import AuditMiddleware
from ormai.store.models import AuditRecord, ErrorInfo
from ormai.store.retention import RetentionManager, RetentionPolicy, RetentionResult

__all__ = [
    # Models
    "AuditRecord",
    "ErrorInfo",
    # Base
    "AuditStore",
    # Implementations
    "JsonlAuditStore",
    # Retention
    "RetentionPolicy",
    "RetentionManager",
    "RetentionResult",
    # Middleware
    "AuditMiddleware",
]

# Optional Peewee audit store (requires peewee to be installed)
try:
    from ormai.store.peewee import BaseAuditRecordModel as PeeweeAuditModel  # noqa: F401
    from ormai.store.peewee import PeeweeAuditStore, create_audit_model  # noqa: F401

    __all__.extend(["PeeweeAuditStore", "PeeweeAuditModel", "create_audit_model"])
except ImportError:
    pass

# Optional SQLAlchemy audit store (requires sqlalchemy to be installed)
try:
    from ormai.store.sqlalchemy import AuditRecordModel as SQLAlchemyAuditModel  # noqa: F401
    from ormai.store.sqlalchemy import SQLAlchemyAuditStore  # noqa: F401

    __all__.extend(["SQLAlchemyAuditStore", "SQLAlchemyAuditModel"])
except ImportError:
    pass

# Optional Tortoise audit store (requires tortoise-orm to be installed)
try:
    from ormai.store.tortoise import AuditRecordModel as TortoiseAuditModel  # noqa: F401
    from ormai.store.tortoise import TortoiseAuditStore  # noqa: F401

    __all__.extend(["TortoiseAuditStore", "TortoiseAuditModel"])
except ImportError:
    pass

# Optional Django audit store (requires Django to be installed)
try:
    from ormai.store.django import AuditRecordModel as DjangoAuditModel  # noqa: F401
    from ormai.store.django import DjangoAuditStore  # noqa: F401

    __all__.extend(["DjangoAuditStore", "DjangoAuditModel"])
except ImportError:
    pass
