"""
OrmAI Quickstart Module.

Provides one-function setup for rapid integration.
"""

from ormai.quickstart.peewee import mount_peewee
from ormai.quickstart.sqlalchemy import mount_sqlalchemy
from ormai.quickstart.tortoise import mount_tortoise

__all__ = [
    "mount_peewee",
    "mount_sqlalchemy",
    "mount_tortoise",
]
