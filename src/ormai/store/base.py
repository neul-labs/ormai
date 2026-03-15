"""
Abstract audit store interface.
"""

from abc import ABC, abstractmethod
from datetime import datetime

from ormai.store.models import AuditRecord


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

    async def store_sync(self, record: AuditRecord) -> None:
        """
        Synchronous wrapper for store.

        Default implementation runs async in event loop.
        """
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create a task if we're in an async context
            asyncio.create_task(self.store(record))
        else:
            loop.run_until_complete(self.store(record))
