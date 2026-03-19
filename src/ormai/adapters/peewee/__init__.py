"""
Peewee adapter for OrmAI.

Provides synchronous database access through Peewee ORM.
"""

from __future__ import annotations

from ormai.adapters.peewee.adapter import PeeweeAdapter
from ormai.adapters.peewee.compiler import PeeweeCompiler
from ormai.adapters.peewee.introspection import PeeweeIntrospector

__all__ = [
    "PeeweeAdapter",
    "PeeweeCompiler",
    "PeeweeIntrospector",
]
