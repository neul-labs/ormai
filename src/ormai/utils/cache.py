"""
Schema cache for memoizing adapter introspection.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ormai.core.types import SchemaMetadata


@dataclass
class CacheEntry:
    """Entry in the persistent cache."""

    schema: dict[str, Any]  # Serialized SchemaMetadata
    timestamp: float
    schema_hash: str | None = None


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


class PersistentSchemaCache:
    """
    Persistent cache for schema metadata with file-based storage.

    Features:
    - Stores schema to disk for cross-process sharing
    - Migration hash-based invalidation
    - TTL support with lazy expiration
    - Thread-safe file operations

    Usage:
        cache = PersistentSchemaCache("/path/to/cache")

        # With migration hash for automatic invalidation
        schema = cache.get_or_build(
            key="myapp",
            builder=adapter.introspect,
            schema_hash=compute_migration_hash(migration_files),
        )
    """

    def __init__(
        self,
        cache_dir: str | Path,
        ttl_seconds: float = 3600,  # 1 hour default
    ) -> None:
        """
        Initialize the persistent cache.

        Args:
            cache_dir: Directory for storing cache files
            ttl_seconds: Time-to-live for cached entries (default 1 hour)
        """
        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = ttl_seconds
        self._memory_cache: dict[str, tuple[SchemaMetadata, float, str | None]] = {}

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_file(self, key: str) -> Path:
        """Get path to cache file for a key."""
        # Use hash for filename to avoid filesystem issues
        safe_key = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{safe_key}.json"

    def get(
        self,
        key: str,
        schema_hash: str | None = None,
    ) -> SchemaMetadata | None:
        """
        Get a cached schema by key.

        Args:
            key: Cache key
            schema_hash: Optional hash to validate against

        Returns:
            None if not cached, expired, or hash mismatch.
        """
        # Check memory cache first
        if key in self._memory_cache:
            schema, timestamp, cached_hash = self._memory_cache[key]
            # Check if expired (TTL)
            if time.time() - timestamp > self.ttl_seconds:
                del self._memory_cache[key]
            elif self._is_valid(timestamp, cached_hash, schema_hash):
                return schema
            else:
                # Hash mismatch but not expired - return None but don't delete
                return None

        # Check disk cache
        cache_file = self._cache_file(key)
        if not cache_file.exists():
            return None

        try:
            with cache_file.open("r") as f:
                data = json.load(f)

            entry = CacheEntry(
                schema=data["schema"],
                timestamp=data["timestamp"],
                schema_hash=data.get("schema_hash"),
            )

            # Check TTL first - only delete on TTL expiration
            if time.time() - entry.timestamp > self.ttl_seconds:
                cache_file.unlink(missing_ok=True)
                return None

            # Check hash (don't delete on mismatch)
            if not self._is_valid(entry.timestamp, entry.schema_hash, schema_hash):
                return None

            # Deserialize schema
            schema = self._deserialize_schema(entry.schema)

            # Update memory cache
            self._memory_cache[key] = (schema, entry.timestamp, entry.schema_hash)

            return schema

        except (json.JSONDecodeError, KeyError, OSError):
            # Corrupted cache file, remove it
            cache_file.unlink(missing_ok=True)
            return None

    def set(
        self,
        key: str,
        schema: SchemaMetadata,
        schema_hash: str | None = None,
    ) -> None:
        """
        Cache a schema with the given key.

        Args:
            key: Cache key
            schema: Schema metadata to cache
            schema_hash: Optional hash for invalidation
        """
        timestamp = time.time()

        # Update memory cache
        self._memory_cache[key] = (schema, timestamp, schema_hash)

        # Write to disk
        cache_file = self._cache_file(key)
        data = {
            "schema": self._serialize_schema(schema),
            "timestamp": timestamp,
            "schema_hash": schema_hash,
        }

        try:
            with cache_file.open("w") as f:
                json.dump(data, f, indent=2)
        except OSError:
            # Disk write failed, but memory cache is updated
            pass

    def get_or_build(
        self,
        key: str,
        builder: Callable[[], SchemaMetadata],
        schema_hash: str | None = None,
    ) -> SchemaMetadata:
        """
        Get cached schema or build and cache it.

        Args:
            key: Cache key
            builder: Function to build schema if not cached
            schema_hash: Optional hash for invalidation
        """
        cached = self.get(key, schema_hash)
        if cached is not None:
            return cached

        schema = builder()
        self.set(key, schema, schema_hash)
        return schema

    def invalidate(self, key: str) -> None:
        """Invalidate a cached entry."""
        self._memory_cache.pop(key, None)
        self._cache_file(key).unlink(missing_ok=True)

    def invalidate_all(self) -> None:
        """Invalidate all cached entries."""
        self._memory_cache.clear()
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink(missing_ok=True)

    def _is_valid(
        self,
        timestamp: float,
        cached_hash: str | None,
        expected_hash: str | None,
    ) -> bool:
        """Check if a cached entry is still valid."""
        # Check TTL
        if time.time() - timestamp > self.ttl_seconds:
            return False

        # Check hash if expected
        if expected_hash is not None and cached_hash != expected_hash:
            return False

        return not (expected_hash is None or cached_hash == expected_hash)

    def _serialize_schema(self, schema: SchemaMetadata) -> dict[str, Any]:
        """Serialize schema to JSON-compatible dict."""
        return schema.model_dump()

    def _deserialize_schema(self, data: dict[str, Any]) -> SchemaMetadata:
        """Deserialize schema from dict."""
        return SchemaMetadata.model_validate(data)

    def __len__(self) -> int:
        """Number of cached entries (files on disk)."""
        return len(list(self.cache_dir.glob("*.json")))


def compute_migration_hash(
    paths: list[str | Path],
    algorithm: str = "sha256",
) -> str:
    """
    Compute a hash from migration files for cache invalidation.

    This can be used to detect when database schema has changed
    and the cache should be invalidated.

    Args:
        paths: List of paths to migration files or directories
        algorithm: Hash algorithm to use (default: sha256)

    Returns:
        Hex digest of the combined hash

    Example:
        hash = compute_migration_hash([
            "alembic/versions/",
            "models.py",
        ])

        schema = cache.get_or_build(
            "main",
            adapter.introspect,
            schema_hash=hash,
        )
    """
    hasher = hashlib.new(algorithm)

    for path in sorted(paths):
        path = Path(path)

        if not path.exists():
            continue

        if path.is_file():
            _hash_file(hasher, path)
        elif path.is_dir():
            for file_path in sorted(path.rglob("*")):
                if file_path.is_file():
                    _hash_file(hasher, file_path)

    return hasher.hexdigest()


def _hash_file(hasher: Any, path: Path) -> None:
    """Add file contents to hasher."""
    try:
        with path.open("rb") as f:
            # Read in chunks for large files
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
    except (OSError, PermissionError):
        # Skip files that can't be read
        pass
