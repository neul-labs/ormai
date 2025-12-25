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


def get_tortoise_adapter():
    """Get the Tortoise ORM adapter class."""
    from ormai.adapters.tortoise import TortoiseAdapter
    return TortoiseAdapter


def get_peewee_adapter():
    """Get the Peewee adapter class."""
    from ormai.adapters.peewee import PeeweeAdapter
    return PeeweeAdapter


def get_django_adapter():
    """Get the Django ORM adapter class."""
    from ormai.adapters.django import DjangoAdapter
    return DjangoAdapter


def get_sqlmodel_adapter():
    """Get the SQLModel adapter class."""
    from ormai.adapters.sqlmodel import SQLModelAdapter
    return SQLModelAdapter
