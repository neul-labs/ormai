"""
Django ORM adapter for OrmAI.

Provides Django model integration with policy-governed queries.

Note: Requires Django to be installed.
Install with: pip install django
"""

try:
    from ormai.adapters.django.adapter import DjangoAdapter
    from ormai.adapters.django.introspection import DjangoIntrospector

    __all__ = [
        "DjangoAdapter",
        "DjangoIntrospector",
    ]
except ImportError:
    # Django not installed
    __all__ = []
