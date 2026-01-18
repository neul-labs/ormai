"""
OrmAI Quickstart Module.

Provides one-function setup for rapid integration.

Each quickstart function handles lazy importing of its dependencies,
so you only need to install the ORM you're using.
"""

from ormai.quickstart.peewee import mount_peewee
from ormai.quickstart.sqlalchemy import mount_sqlalchemy
from ormai.quickstart.tortoise import mount_tortoise

__all__ = [
    "mount_peewee",
    "mount_sqlalchemy",
    "mount_tortoise",
]

# Optional quickstart functions for frameworks that may not be installed
try:
    from ormai.quickstart.django import mount_django  # noqa: F401

    __all__.append("mount_django")
except ImportError:
    pass

try:
    from ormai.quickstart.sqlmodel import mount_sqlmodel  # noqa: F401

    __all__.append("mount_sqlmodel")
except ImportError:
    pass
