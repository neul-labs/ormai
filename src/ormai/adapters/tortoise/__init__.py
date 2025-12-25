"""
Tortoise ORM adapter for OrmAI.

Provides async-first database access through Tortoise ORM.
"""

from __future__ import annotations

from ormai.adapters.tortoise.adapter import TortoiseAdapter
from ormai.adapters.tortoise.compiler import TortoiseCompiler
from ormai.adapters.tortoise.introspection import TortoiseIntrospector

__all__ = [
    "TortoiseAdapter",
    "TortoiseCompiler",
    "TortoiseIntrospector",
]
