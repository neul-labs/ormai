"""
JSONL file-based audit store.

A simple file-based implementation for development and testing.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ormai.store.base import AuditStore
from ormai.store.models import AuditRecord


class JsonlAuditStore(AuditStore):
    """
    Audit store that writes records to a JSONL file.

    Each line in the file is a JSON-encoded audit record.
    This is suitable for development and small-scale deployments.
    """

    def __init__(self, path: str | Path) -> None:
        """
        Initialize the JSONL store.

        Args:
            path: Path to the JSONL file
        """
        self.path = Path(path)
        # Ensure directory exists
        self.path.parent.mkdir(parents=True, exist_ok=True)

    async def store(self, record: AuditRecord) -> None:
        """Append a record to the JSONL file."""
        data = self._serialize_record(record)
        line = json.dumps(data, default=str) + "\n"

        # Append to file
        with open(self.path, "a") as f:
            f.write(line)

    async def get(self, record_id: str) -> AuditRecord | None:
        """Find a record by ID."""
        if not self.path.exists():
            return None

        with open(self.path) as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                if data.get("id") == record_id:
                    return self._deserialize_record(data)

        return None

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
        """Query records with filters."""
        if not self.path.exists():
            return []

        results: list[AuditRecord] = []
        skipped = 0

        with open(self.path) as f:
            for line in f:
                if not line.strip():
                    continue

                data = json.loads(line)

                # Apply filters
                if tenant_id and data.get("tenant_id") != tenant_id:
                    continue
                if principal_id and data.get("principal_id") != principal_id:
                    continue
                if tool_name and data.get("tool_name") != tool_name:
                    continue

                record_time = datetime.fromisoformat(data["timestamp"])
                if start_time and record_time < start_time:
                    continue
                if end_time and record_time > end_time:
                    continue

                # Handle offset
                if skipped < offset:
                    skipped += 1
                    continue

                # Add to results
                results.append(self._deserialize_record(data))

                # Check limit
                if len(results) >= limit:
                    break

        return results

    async def count(
        self,
        *,
        tenant_id: str | None = None,
        principal_id: str | None = None,
        tool_name: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> int:
        """Count records matching filters."""
        if not self.path.exists():
            return 0

        count = 0

        with open(self.path) as f:
            for line in f:
                if not line.strip():
                    continue

                data = json.loads(line)

                # Apply filters
                if tenant_id and data.get("tenant_id") != tenant_id:
                    continue
                if principal_id and data.get("principal_id") != principal_id:
                    continue
                if tool_name and data.get("tool_name") != tool_name:
                    continue

                record_time = datetime.fromisoformat(data["timestamp"])
                if start_time and record_time < start_time:
                    continue
                if end_time and record_time > end_time:
                    continue

                count += 1

        return count

    def _serialize_record(self, record: AuditRecord) -> dict[str, Any]:
        """Serialize a record for JSON storage."""
        data = record.model_dump()
        data["timestamp"] = record.timestamp.isoformat()
        return data

    def _deserialize_record(self, data: dict[str, Any]) -> AuditRecord:
        """Deserialize a record from JSON storage."""
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return AuditRecord.model_validate(data)

    async def delete_before(self, before: datetime) -> int:
        """
        Delete records older than the specified timestamp.

        This rewrites the entire file, keeping only records newer than the cutoff.

        Args:
            before: Delete records with timestamp before this datetime

        Returns:
            Number of records deleted
        """
        if not self.path.exists():
            return 0

        # Read all records and filter
        records_to_keep: list[str] = []
        deleted_count = 0

        with open(self.path) as f:
            for line in f:
                if not line.strip():
                    continue

                data = json.loads(line)
                record_time = datetime.fromisoformat(data["timestamp"])

                if record_time < before:
                    deleted_count += 1
                else:
                    records_to_keep.append(line)

        # Rewrite file with remaining records
        if deleted_count > 0:
            with open(self.path, "w") as f:
                f.writelines(records_to_keep)

        return deleted_count

    def clear(self) -> None:
        """Clear all records (for testing)."""
        if self.path.exists():
            self.path.unlink()
