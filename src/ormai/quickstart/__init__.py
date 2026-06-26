"""
OrmAI Quickstart Module.

Provides one-function setup for rapid integration.

Each quickstart function handles lazy importing of its dependencies,
so you only need to install the ORM you're using.
"""

__all__: list[str] = []

# Optional quickstart functions for ORMs/frameworks that may not be installed
try:
    from ormai.quickstart.peewee import mount_peewee  # noqa: F401

    __all__.append("mount_peewee")
except ImportError:
    pass

try:
    from ormai.quickstart.sqlalchemy import mount_sqlalchemy  # noqa: F401

    __all__.append("mount_sqlalchemy")
except ImportError:
    pass

try:
    from ormai.quickstart.tortoise import mount_tortoise  # noqa: F401

    __all__.append("mount_tortoise")
except ImportError:
    pass

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
