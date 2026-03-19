"""
OrmAI Store Module.

Provides audit logging infrastructure and optional conversation history.
"""

from ormai.store.base import AuditStore
from ormai.store.jsonl import JsonlAuditStore
from ormai.store.middleware import AuditMiddleware
from ormai.store.models import AuditRecord, ErrorInfo
from ormai.store.peewee import BaseAuditRecordModel as PeeweeAuditModel
from ormai.store.peewee import PeeweeAuditStore, create_audit_model
from ormai.store.tortoise import AuditRecordModel as TortoiseAuditModel
from ormai.store.tortoise import TortoiseAuditStore

__all__ = [
    # Models
    "AuditRecord",
    "ErrorInfo",
    # Base
    "AuditStore",
    # Implementations
    "JsonlAuditStore",
    "TortoiseAuditStore",
    "TortoiseAuditModel",
    "PeeweeAuditStore",
    "PeeweeAuditModel",
    "create_audit_model",
    # Middleware
    "AuditMiddleware",
]
