"""Tests for persistent schema cache."""

import tempfile
import time
from pathlib import Path

import pytest

from ormai.core.types import FieldMetadata, FieldType, ModelMetadata, SchemaMetadata
from ormai.utils.cache import PersistentSchemaCache, compute_migration_hash


@pytest.fixture
def cache_dir():
    """Create a temporary cache directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_schema():
    """Create a sample schema for testing."""
    return SchemaMetadata(
        models={
            "Customer": ModelMetadata(
                name="Customer",
                table_name="customers",
                fields={
                    "id": FieldMetadata(
                        name="id",
                        field_type=FieldType.INTEGER.value,
                        nullable=False,
                        primary_key=True,
                    ),
                    "name": FieldMetadata(
                        name="name",
                        field_type=FieldType.STRING.value,
                        nullable=False,
                    ),
                },
                primary_key="id",
            ),
        },
    )


class TestPersistentSchemaCache:
    """Tests for PersistentSchemaCache."""

    def test_set_and_get(self, cache_dir, sample_schema):
        """Test basic set and get operations."""
        cache = PersistentSchemaCache(cache_dir)

        cache.set("myapp", sample_schema)
        retrieved = cache.get("myapp")

        assert retrieved is not None
        assert "Customer" in retrieved.models
        assert "id" in retrieved.models["Customer"].fields

    def test_get_nonexistent(self, cache_dir):
        """Test getting a non-existent key."""
        cache = PersistentSchemaCache(cache_dir)

        result = cache.get("nonexistent")

        assert result is None

    def test_persistence_across_instances(self, cache_dir, sample_schema):
        """Test that cache persists across cache instances."""
        cache1 = PersistentSchemaCache(cache_dir)
        cache1.set("myapp", sample_schema)

        # Create a new cache instance
        cache2 = PersistentSchemaCache(cache_dir)
        retrieved = cache2.get("myapp")

        assert retrieved is not None
        assert "Customer" in retrieved.models

    def test_ttl_expiration(self, cache_dir, sample_schema):
        """Test TTL expiration."""
        cache = PersistentSchemaCache(cache_dir, ttl_seconds=0.1)

        cache.set("myapp", sample_schema)
        assert cache.get("myapp") is not None

        # Wait for expiration
        time.sleep(0.2)
        assert cache.get("myapp") is None

    def test_hash_validation(self, cache_dir, sample_schema):
        """Test schema hash validation."""
        cache = PersistentSchemaCache(cache_dir)

        # Set with hash
        cache.set("myapp", sample_schema, schema_hash="hash1")

        # Get with matching hash
        assert cache.get("myapp", schema_hash="hash1") is not None

        # Get with different hash
        assert cache.get("myapp", schema_hash="hash2") is None

    def test_hash_invalidation(self, cache_dir, sample_schema):
        """Test that different hash invalidates cache."""
        cache = PersistentSchemaCache(cache_dir)

        cache.set("myapp", sample_schema, schema_hash="v1")

        # Different hash should not match
        result = cache.get("myapp", schema_hash="v2")
        assert result is None

        # No hash requirement should still work
        result = cache.get("myapp")
        assert result is not None

    def test_get_or_build(self, cache_dir, sample_schema):
        """Test get_or_build functionality."""
        cache = PersistentSchemaCache(cache_dir)
        build_count = 0

        def builder():
            nonlocal build_count
            build_count += 1
            return sample_schema

        # First call builds
        result1 = cache.get_or_build("myapp", builder)
        assert build_count == 1
        assert result1 is not None

        # Second call uses cache
        result2 = cache.get_or_build("myapp", builder)
        assert build_count == 1  # Not incremented
        assert result2 is not None

    def test_get_or_build_with_hash(self, cache_dir, sample_schema):
        """Test get_or_build with schema hash."""
        cache = PersistentSchemaCache(cache_dir)
        build_count = 0

        def builder():
            nonlocal build_count
            build_count += 1
            return sample_schema

        # First call builds with hash
        cache.get_or_build("myapp", builder, schema_hash="v1")
        assert build_count == 1

        # Same hash uses cache
        cache.get_or_build("myapp", builder, schema_hash="v1")
        assert build_count == 1

        # Different hash rebuilds
        cache.get_or_build("myapp", builder, schema_hash="v2")
        assert build_count == 2

    def test_invalidate(self, cache_dir, sample_schema):
        """Test invalidation."""
        cache = PersistentSchemaCache(cache_dir)

        cache.set("myapp", sample_schema)
        assert cache.get("myapp") is not None

        cache.invalidate("myapp")
        assert cache.get("myapp") is None

    def test_invalidate_all(self, cache_dir, sample_schema):
        """Test invalidating all entries."""
        cache = PersistentSchemaCache(cache_dir)

        cache.set("app1", sample_schema)
        cache.set("app2", sample_schema)
        assert len(cache) == 2

        cache.invalidate_all()
        assert len(cache) == 0

    def test_len(self, cache_dir, sample_schema):
        """Test __len__."""
        cache = PersistentSchemaCache(cache_dir)

        assert len(cache) == 0

        cache.set("app1", sample_schema)
        assert len(cache) == 1

        cache.set("app2", sample_schema)
        assert len(cache) == 2

    def test_memory_cache(self, cache_dir, sample_schema):
        """Test that memory cache is used after disk read."""
        cache = PersistentSchemaCache(cache_dir)

        cache.set("myapp", sample_schema)

        # Clear memory cache to force disk read
        cache._memory_cache.clear()

        # First get reads from disk
        cache.get("myapp")

        # Memory cache should now be populated
        assert "myapp" in cache._memory_cache

    def test_corrupted_cache_file(self, cache_dir, sample_schema):
        """Test handling of corrupted cache files."""
        cache = PersistentSchemaCache(cache_dir)

        cache.set("myapp", sample_schema)

        # Corrupt the cache file
        cache_file = cache._cache_file("myapp")
        cache_file.write_text("invalid json {{{")

        # Clear memory cache
        cache._memory_cache.clear()

        # Get should handle corruption gracefully
        result = cache.get("myapp")
        assert result is None

        # File should be removed
        assert not cache_file.exists()


class TestComputeMigrationHash:
    """Tests for compute_migration_hash."""

    def test_hash_single_file(self):
        """Test hashing a single file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "migration.py"
            file_path.write_text("CREATE TABLE users (id INT);")

            hash1 = compute_migration_hash([file_path])

            assert hash1 is not None
            assert len(hash1) == 64  # SHA256 hex length

    def test_hash_changes_with_content(self):
        """Test that hash changes when file content changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "migration.py"

            file_path.write_text("v1 content")
            hash1 = compute_migration_hash([file_path])

            file_path.write_text("v2 content")
            hash2 = compute_migration_hash([file_path])

            assert hash1 != hash2

    def test_hash_directory(self):
        """Test hashing a directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            migrations = Path(tmpdir) / "migrations"
            migrations.mkdir()
            (migrations / "001.py").write_text("migration 1")
            (migrations / "002.py").write_text("migration 2")

            hash1 = compute_migration_hash([migrations])

            assert hash1 is not None

    def test_hash_deterministic(self):
        """Test that hash is deterministic."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "migration.py"
            file_path.write_text("content")

            hash1 = compute_migration_hash([file_path])
            hash2 = compute_migration_hash([file_path])

            assert hash1 == hash2

    def test_hash_empty_paths(self):
        """Test hashing empty paths list."""
        hash1 = compute_migration_hash([])

        # Should return empty hash (SHA256 of nothing)
        assert hash1 is not None

    def test_hash_nonexistent_path(self):
        """Test hashing non-existent path."""
        hash1 = compute_migration_hash(["/nonexistent/path"])

        # Should handle gracefully
        assert hash1 is not None

    def test_hash_multiple_files(self):
        """Test hashing multiple files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "migration1.py"
            file2 = Path(tmpdir) / "migration2.py"
            file1.write_text("migration 1")
            file2.write_text("migration 2")

            hash1 = compute_migration_hash([file1, file2])

            assert hash1 is not None

    def test_hash_algorithm(self):
        """Test different hash algorithms."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "migration.py"
            file_path.write_text("content")

            sha256_hash = compute_migration_hash([file_path], algorithm="sha256")
            md5_hash = compute_migration_hash([file_path], algorithm="md5")

            assert len(sha256_hash) == 64
            assert len(md5_hash) == 32
