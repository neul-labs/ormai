"""
OrmAI - ORM-native capability runtime for safe, typed, auditable agent database access.

OrmAI turns existing SQLAlchemy, Tortoise, and Peewee models into a safe, typed,
auditable tool surface for agents. It layers policy-compiled data access, tenant
isolation, and audit logging on top of your current application without exposing
direct ORM handles to the LLM.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("ormai")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"

from ormai.core.context import Principal, RunContext
from ormai.core.errors import (
    FieldNotAllowedError,
    ModelNotAllowedError,
    OrmAIError,
    QueryBudgetExceededError,
    QueryTooBroadError,
    RelationNotAllowedError,
    TenantScopeRequiredError,
    ValidationError,
)

__all__ = [
    # Version
    "__version__",
    # Context
    "Principal",
    "RunContext",
    # Errors
    "OrmAIError",
    "ModelNotAllowedError",
    "FieldNotAllowedError",
    "RelationNotAllowedError",
    "TenantScopeRequiredError",
    "QueryTooBroadError",
    "QueryBudgetExceededError",
    "ValidationError",
]
