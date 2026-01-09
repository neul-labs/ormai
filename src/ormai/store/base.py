"""
Abstract audit store interface.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime

from ormai.store.models import AuditRecord

logger = logging.getLogger(__name__)


class AuditStore(ABC):
    """
    Abstract base class for audit log storage.

    Implementations can store audit records in various backends:
    - SQL databases
    - Document stores
    - File systems
    - Cloud services
    """

    @abstractmethod
    async def store(self, record: AuditRecord) -> None:
        """
        Store an audit record.

        This should be called after every tool execution.
        """
        ...

    @abstractmethod
    async def get(self, record_id: str) -> AuditRecord | None:
        """
        Retrieve an audit record by ID.
        """
        ...

    @abstractmethod
    async def query(
        self,
        *,
        tenant_id: str | None = None,
        principal_id: str | None = None,
        tool_name: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditRecord]:
        """
        Query audit records with filters.
        """
        ...

    @abstractmethod
    async def count(
        self,
        *,
        tenant_id: str | None = None,
        principal_id: str | None = None,
        tool_name: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> int:
        """
        Count audit records matching filters.

        Returns the total count without retrieving records.
        """
        ...

    async def bulk_store(self, records: list[AuditRecord]) -> int:
        """
        Store multiple audit records in a single operation.

        Default implementation calls store() in a loop.
        Override in implementations for optimized batch inserts.

        Args:
            records: List of audit records to store

        Returns:
            Number of records stored
        """
        for record in records:
            await self.store(record)
        return len(records)

    async def delete_before(self, before: datetime) -> int:
        """
        Delete audit records older than the specified timestamp.

        Used for retention policy cleanup.
        Override in implementations that support deletion.

        Args:
            before: Delete records with timestamp before this datetime

        Returns:
            Number of records deleted

        Raises:
            NotImplementedError: If the store doesn't support deletion
        """
        raise NotImplementedError("Retention cleanup not supported by this store")

    def store_sync(self, record: AuditRecord) -> None:
        """
        Synchronous wrapper for store.

        Default implementation runs async in a new event loop.
        Note: This creates a new event loop for each call. For better performance
        in high-throughput scenarios, consider using an async-aware storage backend.
        """
        try:
            # Try to get the running loop (for Jupyter, etc.)
            asyncio.get_running_loop()
        except RuntimeError:
            # No running loop, safe to create a new one
            asyncio.run(self.store(record))
        else:
            # We're in an async context - schedule the task with error handling
            async def _store_and_log():
                try:
                    await self.store(record)
                except Exception as e:
                    logger.error(f"Failed to store audit record: {e}")

            asyncio.create_task(_store_and_log())
