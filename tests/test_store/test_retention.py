"""Tests for retention policy and manager."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from ormai.store.retention import RetentionManager, RetentionPolicy, RetentionResult


class TestRetentionPolicy:
    def test_defaults(self):
        policy = RetentionPolicy()
        assert policy.max_age == timedelta(days=90)
        assert policy.archive_before_delete is False
        assert policy.archive_path is None
        assert policy.run_interval == timedelta(hours=24)
        assert policy.min_records_to_keep == 0

    def test_days_classmethod(self):
        policy = RetentionPolicy.days(30)
        assert policy.max_age == timedelta(days=30)

    def test_no_retention_classmethod(self):
        policy = RetentionPolicy.no_retention()
        assert policy.max_age == timedelta.max

    def test_archive_without_path_raises(self):
        with pytest.raises(ValueError, match="archive_path"):
            RetentionPolicy(archive_before_delete=True)

    def test_archive_path_string_converted_to_path(self):
        from pathlib import Path

        policy = RetentionPolicy(
            archive_before_delete=True,
            archive_path="/tmp/archive",
        )
        assert isinstance(policy.archive_path, Path)

    def test_custom_values(self):
        policy = RetentionPolicy(
            max_age=timedelta(days=7),
            run_interval=timedelta(hours=1),
            min_records_to_keep=100,
        )
        assert policy.max_age == timedelta(days=7)
        assert policy.run_interval == timedelta(hours=1)
        assert policy.min_records_to_keep == 100


class TestRetentionResult:
    def test_success_with_no_error(self):
        result = RetentionResult(records_deleted=5, cutoff_time=datetime.now(timezone.utc))
        assert result.success is True

    def test_failure_with_error(self):
        result = RetentionResult(error="Something went wrong")
        assert result.success is False

    def test_default_values(self):
        result = RetentionResult()
        assert result.records_deleted == 0
        assert result.records_archived == 0
        assert result.cutoff_time is None
        assert result.duration_ms == 0.0
        assert result.error is None


class TestRetentionManager:
    @pytest.fixture
    def mock_store(self):
        store = AsyncMock()
        store.delete_before = AsyncMock(return_value=5)
        store.query = AsyncMock(return_value=[])
        return store

    @pytest.fixture
    def manager(self, mock_store):
        return RetentionManager(
            store=mock_store,
            policy=RetentionPolicy.days(30),
        )

    @pytest.mark.asyncio
    async def test_run_cleanup_success(self, manager, mock_store):
        result = await manager.run_cleanup()
        assert result.success is True
        assert result.records_deleted == 5
        assert result.cutoff_time is not None
        assert result.duration_ms > 0
        mock_store.delete_before.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_cleanup_not_implemented(self, mock_store):
        mock_store.delete_before = AsyncMock(side_effect=NotImplementedError)

        manager = RetentionManager(store=mock_store, policy=RetentionPolicy.days(30))
        result = await manager.run_cleanup()
        assert result.success is False
        assert "does not support" in result.error

    @pytest.mark.asyncio
    async def test_run_cleanup_generic_error(self, mock_store):
        mock_store.delete_before = AsyncMock(side_effect=RuntimeError("Disk full"))

        manager = RetentionManager(store=mock_store, policy=RetentionPolicy.days(30))
        result = await manager.run_cleanup()
        assert result.success is False
        assert "Disk full" in result.error

    @pytest.mark.asyncio
    async def test_run_cleanup_with_archive(self, tmp_path, mock_store):
        archive_record = AsyncMock()
        archive_record.timestamp = datetime.now(timezone.utc)
        archive_record.model_dump = MagicMock(return_value={"id": "test", "timestamp": "2024-01-01T00:00:00Z"})
        mock_store.query = AsyncMock(return_value=[archive_record])

        archive_dir = tmp_path / "archive_dir"
        archive_dir.mkdir()

        manager = RetentionManager(
            store=mock_store,
            policy=RetentionPolicy(
                max_age=timedelta(days=30),
                archive_before_delete=True,
                archive_path=str(archive_dir),
            ),
        )
        result = await manager.run_cleanup()
        assert result.success is True

    @pytest.mark.asyncio
    async def test_run_cleanup_no_archive_path(self, mock_store):
        manager = RetentionManager(
            store=mock_store,
            policy=RetentionPolicy(
                max_age=timedelta(days=30),
                archive_before_delete=False,
                archive_path=None,
            ),
        )
        result = await manager.run_cleanup()
        assert result.success is True
        assert result.records_archived == 0

    def test_is_running_default(self, manager):
        assert manager.is_running is False