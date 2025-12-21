"""
Schema cache for memoizing adapter introspection.
"""

import time
from collections.abc import Callable

from ormai.core.types import SchemaMetadata


class SchemaCache:
    """
    Cache for schema metadata.

    Memoizes adapter introspection results with optional TTL.
    """

    def __init__(self, ttl_seconds: float = 300) -> None:
        """
        Initialize the cache.

        Args:
            ttl_seconds: Time-to-live for cached entries (default 5 minutes)
        """
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, tuple[SchemaMetadata, float]] = {}

    def get(self, key: str) -> SchemaMetadata | None:
        """
        Get a cached schema by key.

        Returns None if not cached or expired.
        """
        if key not in self._cache:
            return None

        schema, timestamp = self._cache[key]
        if time.time() - timestamp > self.ttl_seconds:
            del self._cache[key]
            return None

        return schema

    def set(self, key: str, schema: SchemaMetadata) -> None:
        """
        Cache a schema with the given key.
        """
        self._cache[key] = (schema, time.time())

    def get_or_build(
        self,
        key: str,
        builder: Callable[[], SchemaMetadata],
    ) -> SchemaMetadata:
        """
        Get cached schema or build and cache it.

        Args:
            key: Cache key
            builder: Function to build schema if not cached
        """
        cached = self.get(key)
        if cached is not None:
            return cached

        schema = builder()
        self.set(key, schema)
        return schema

    def invalidate(self, key: str) -> None:
        """
        Invalidate a cached entry.
        """
        self._cache.pop(key, None)

    def invalidate_all(self) -> None:
        """
        Invalidate all cached entries.
        """
        self._cache.clear()

    def __len__(self) -> int:
        """Number of cached entries."""
        return len(self._cache)
