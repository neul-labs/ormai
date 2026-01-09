"""
Audit log retention policy and management.

Provides automated cleanup of old audit records based on configurable
retention policies.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ormai.store.base import AuditStore

logger = logging.getLogger(__name__)


@dataclass
class RetentionPolicy:
    """
    Configuration for audit log retention.

    Attributes:
        max_age: Maximum age of records to keep (records older than this are deleted)
        archive_before_delete: If True, archive records before deleting
        archive_path: Path for archived records (required if archive_before_delete is True)
        run_interval: How often to run the cleanup task
        min_records_to_keep: Always keep at least this many records (0 = no minimum)
    """

    max_age: timedelta = field(default_factory=lambda: timedelta(days=90))
    archive_before_delete: bool = False
    archive_path: Path | str | None = None
    run_interval: timedelta = field(default_factory=lambda: timedelta(hours=24))
    min_records_to_keep: int = 0

    def __post_init__(self) -> None:
        if self.archive_before_delete and not self.archive_path:
            raise ValueError("archive_path is required when archive_before_delete is True")
        if self.archive_path and isinstance(self.archive_path, str):
            self.archive_path = Path(self.archive_path)

    @classmethod
    def days(cls, days: int, **kwargs: Any) -> RetentionPolicy:
        """Create a policy with max_age in days."""
        return cls(max_age=timedelta(days=days), **kwargs)

    @classmethod
    def no_retention(cls) -> RetentionPolicy:
        """Create a policy that keeps all records (no cleanup)."""
        return cls(max_age=timedelta.max)


@dataclass
class RetentionResult:
    """
    Result of a retention cleanup run.

    Attributes:
        records_deleted: Number of records deleted
        records_archived: Number of records archived (if archiving enabled)
        cutoff_time: The timestamp used as the cutoff
        duration_ms: Time taken to run cleanup in milliseconds
        error: Error message if cleanup failed
    """

    records_deleted: int = 0
    records_archived: int = 0
    cutoff_time: datetime | None = None
    duration_ms: float = 0.0
    error: str | None = None

    @property
    def success(self) -> bool:
        """Check if the cleanup was successful."""
        return self.error is None


class RetentionManager:
    """
    Manages audit log retention based on policy.

    Provides methods for running cleanup on-demand or scheduling
    periodic cleanup tasks.

    Usage:
        manager = RetentionManager(
            store=audit_store,
            policy=RetentionPolicy.days(90),
        )

        # Run cleanup once
        result = await manager.run_cleanup()

        # Or schedule periodic cleanup
        await manager.start_scheduler()
    """

    def __init__(
        self,
        store: AuditStore,
        policy: RetentionPolicy | None = None,
    ) -> None:
        """
        Initialize the retention manager.

        Args:
            store: The audit store to manage
            policy: Retention policy (defaults to 90 days)
        """
        self.store = store
        self.policy = policy or RetentionPolicy()
        self._scheduler_task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event = asyncio.Event()

    async def run_cleanup(self) -> RetentionResult:
        """
        Run a single cleanup pass.

        Deletes records older than the policy's max_age.

        Returns:
            RetentionResult with cleanup statistics
        """
        import time

        start_time = time.perf_counter()
        cutoff = datetime.now(timezone.utc) - self.policy.max_age

        result = RetentionResult(cutoff_time=cutoff)

        try:
            # Archive if enabled
            if self.policy.archive_before_delete and self.policy.archive_path:
                archived = await self._archive_records(cutoff)
                result.records_archived = archived

            # Delete old records
            deleted = await self.store.delete_before(cutoff)
            result.records_deleted = deleted

            logger.info(
                "Retention cleanup completed: deleted=%d, archived=%d, cutoff=%s",
                deleted,
                result.records_archived,
                cutoff.isoformat(),
            )

        except NotImplementedError:
            result.error = "Store does not support retention cleanup"
            logger.warning(
                "Retention cleanup skipped: %s does not support delete_before",
                type(self.store).__name__,
            )
        except Exception as e:
            result.error = str(e)
            logger.error("Retention cleanup failed: %s", e)

        result.duration_ms = (time.perf_counter() - start_time) * 1000
        return result

    async def _archive_records(self, before: datetime) -> int:
        """Archive records before the cutoff time."""
        if not self.policy.archive_path:
            return 0

        archive_path = Path(self.policy.archive_path)
        archive_path.parent.mkdir(parents=True, exist_ok=True)

        # Query records to archive
        records = await self.store.query(end_time=before, limit=10000)

        if not records:
            return 0

        # Write to archive file
        import json

        archive_file = archive_path / f"archive_{before.strftime('%Y%m%d_%H%M%S')}.jsonl"
        with open(archive_file, "w") as f:
            for record in records:
                data = record.model_dump()
                data["timestamp"] = record.timestamp.isoformat()
                f.write(json.dumps(data, default=str) + "\n")

        logger.info("Archived %d records to %s", len(records), archive_file)
        return len(records)

    async def start_scheduler(self) -> None:
        """
        Start the background scheduler for periodic cleanup.

        The scheduler runs cleanup at the interval specified in the policy.
        Call stop_scheduler() to stop the background task.
        """
        if self._scheduler_task is not None:
            logger.warning("Scheduler already running")
            return

        self._stop_event.clear()
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info(
            "Retention scheduler started (interval=%s)",
            self.policy.run_interval,
        )

    async def stop_scheduler(self) -> None:
        """Stop the background scheduler."""
        if self._scheduler_task is None:
            return

        self._stop_event.set()
        self._scheduler_task.cancel()

        with contextlib.suppress(asyncio.CancelledError):
            await self._scheduler_task

        self._scheduler_task = None
        logger.info("Retention scheduler stopped")

    async def _scheduler_loop(self) -> None:
        """Background loop that runs cleanup periodically."""
        while not self._stop_event.is_set():
            try:
                await self.run_cleanup()
            except Exception as e:
                logger.error("Scheduled retention cleanup failed: %s", e)

            # Wait for the next run or until stopped
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.policy.run_interval.total_seconds(),
                )
                break  # Stop event was set
            except asyncio.TimeoutError:
                pass  # Continue to next run

    @property
    def is_running(self) -> bool:
        """Check if the scheduler is running."""
        return self._scheduler_task is not None and not self._scheduler_task.done()
