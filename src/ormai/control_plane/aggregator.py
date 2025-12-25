"""
Audit Log Aggregator.

Collects and queries audit logs from multiple OrmAI instances.
Provides cross-instance querying, statistics, and analytics.
"""

import asyncio
import statistics
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any

from ormai.control_plane.models import (
    AuditQuery,
    AuditQueryResult,
    AuditStats,
    Instance,
)
from ormai.store.base import AuditStore
from ormai.store.models import AuditRecord


class AuditAggregator(ABC):
    """
    Abstract interface for audit log aggregation.

    Aggregates audit logs from multiple instances and provides
    unified querying and analytics.
    """

    @abstractmethod
    async def register_store(
        self,
        instance_id: str,
        store: AuditStore,
    ) -> None:
        """
        Register an audit store for an instance.
        """
        ...

    @abstractmethod
    async def unregister_store(self, instance_id: str) -> None:
        """
        Unregister an audit store.
        """
        ...

    @abstractmethod
    async def ingest(
        self,
        instance_id: str,
        record: AuditRecord,
    ) -> None:
        """
        Ingest an audit record from an instance.

        Called by instances to push records to the aggregator.
        """
        ...

    @abstractmethod
    async def query(self, query: AuditQuery) -> AuditQueryResult:
        """
        Query audit records across instances.
        """
        ...

    @abstractmethod
    async def get_stats(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        instance_id: str | None = None,
    ) -> AuditStats:
        """
        Get aggregated statistics.
        """
        ...

    @abstractmethod
    async def get_recent(
        self,
        limit: int = 50,
        instance_id: str | None = None,
    ) -> list[AuditRecord]:
        """
        Get the most recent audit records.
        """
        ...


class InMemoryAuditAggregator(AuditAggregator):
    """
    In-memory audit aggregator for testing and development.

    Stores all records in memory with optional size limits.
    """

    def __init__(
        self,
        max_records: int = 100000,
        retention_hours: int = 24,
    ) -> None:
        self._records: list[tuple[str, AuditRecord]] = []  # (instance_id, record)
        self._stores: dict[str, AuditStore] = {}
        self._max_records = max_records
        self._retention_hours = retention_hours

    async def register_store(
        self,
        instance_id: str,
        store: AuditStore,
    ) -> None:
        self._stores[instance_id] = store

    async def unregister_store(self, instance_id: str) -> None:
        self._stores.pop(instance_id, None)

    async def ingest(
        self,
        instance_id: str,
        record: AuditRecord,
    ) -> None:
        self._records.append((instance_id, record))

        # Trim old records
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]

        # Remove expired records
        cutoff = datetime.utcnow() - timedelta(hours=self._retention_hours)
        self._records = [
            (iid, r) for iid, r in self._records if r.timestamp > cutoff
        ]

    async def query(self, query: AuditQuery) -> AuditQueryResult:
        filtered = []

        for instance_id, record in self._records:
            # Filter by instance
            if query.instance_id and instance_id != query.instance_id:
                continue

            # Filter by instance tags (would need instance registry)
            # Skip for now in in-memory implementation

            # Filter by tenant
            if query.tenant_id and record.tenant_id != query.tenant_id:
                continue

            # Filter by principal
            if query.principal_id and record.principal_id != query.principal_id:
                continue

            # Filter by tool
            if query.tool_name and record.tool_name != query.tool_name:
                continue

            # Filter by time range
            if query.start_time and record.timestamp < query.start_time:
                continue
            if query.end_time and record.timestamp > query.end_time:
                continue

            # Filter by errors only
            if query.errors_only and record.error is None:
                continue

            # Filter by model (check inputs)
            if query.model:
                model_in_inputs = record.inputs.get("model") == query.model
                if not model_in_inputs:
                    continue

            filtered.append((instance_id, record))

        # Sort
        reverse = query.sort_desc
        if query.sort_by == "timestamp":
            filtered.sort(key=lambda x: x[1].timestamp, reverse=reverse)
        elif query.sort_by == "duration_ms":
            filtered.sort(
                key=lambda x: x[1].duration_ms or 0, reverse=reverse
            )

        total_count = len(filtered)

        # Pagination
        paginated = filtered[query.offset : query.offset + query.limit]

        return AuditQueryResult(
            records=[r for _, r in paginated],
            total_count=total_count,
            query=query,
            instances_queried=list(set(iid for iid, _ in self._records)),
        )

    async def get_stats(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        instance_id: str | None = None,
    ) -> AuditStats:
        if start_time is None:
            start_time = datetime.utcnow() - timedelta(hours=1)
        if end_time is None:
            end_time = datetime.utcnow()

        # Filter records in time range
        records = []
        for iid, record in self._records:
            if instance_id and iid != instance_id:
                continue
            if record.timestamp < start_time or record.timestamp > end_time:
                continue
            records.append((iid, record))

        if not records:
            return AuditStats(
                start_time=start_time,
                end_time=end_time,
            )

        # Compute stats
        calls_by_tool: dict[str, int] = {}
        calls_by_model: dict[str, int] = {}
        calls_by_instance: dict[str, int] = {}
        errors_by_type: dict[str, int] = {}
        latencies: list[float] = []
        total_rows = 0

        for iid, record in records:
            # By tool
            calls_by_tool[record.tool_name] = (
                calls_by_tool.get(record.tool_name, 0) + 1
            )

            # By model (from inputs)
            model = record.inputs.get("model")
            if model:
                calls_by_model[model] = calls_by_model.get(model, 0) + 1

            # By instance
            calls_by_instance[iid] = calls_by_instance.get(iid, 0) + 1

            # Errors
            if record.error:
                error_type = record.error.type
                errors_by_type[error_type] = errors_by_type.get(error_type, 0) + 1

            # Latency
            if record.duration_ms is not None:
                latencies.append(record.duration_ms)

            # Rows
            if record.row_count is not None:
                total_rows += record.row_count

        # Compute latency percentiles
        latencies.sort()
        n = len(latencies)

        def percentile(p: float) -> float:
            if not latencies:
                return 0.0
            idx = int(n * p / 100)
            return latencies[min(idx, n - 1)]

        return AuditStats(
            start_time=start_time,
            end_time=end_time,
            total_calls=len(records),
            calls_by_tool=calls_by_tool,
            calls_by_model=calls_by_model,
            calls_by_instance=calls_by_instance,
            total_errors=sum(errors_by_type.values()),
            errors_by_type=errors_by_type,
            avg_latency_ms=statistics.mean(latencies) if latencies else 0.0,
            p50_latency_ms=percentile(50),
            p95_latency_ms=percentile(95),
            p99_latency_ms=percentile(99),
            total_rows_returned=total_rows,
            avg_rows_per_query=total_rows / len(records) if records else 0.0,
        )

    async def get_recent(
        self,
        limit: int = 50,
        instance_id: str | None = None,
    ) -> list[AuditRecord]:
        records = self._records
        if instance_id:
            records = [(iid, r) for iid, r in records if iid == instance_id]

        # Sort by timestamp descending
        records.sort(key=lambda x: x[1].timestamp, reverse=True)

        return [r for _, r in records[:limit]]


class FederatedAuditAggregator(AuditAggregator):
    """
    Federated audit aggregator that queries multiple audit stores.

    Does not store records centrally - queries are distributed to
    registered stores and results are merged.
    """

    def __init__(self, timeout_seconds: float = 5.0) -> None:
        self._stores: dict[str, AuditStore] = {}
        self._timeout = timeout_seconds

    async def register_store(
        self,
        instance_id: str,
        store: AuditStore,
    ) -> None:
        self._stores[instance_id] = store

    async def unregister_store(self, instance_id: str) -> None:
        self._stores.pop(instance_id, None)

    async def ingest(
        self,
        instance_id: str,
        record: AuditRecord,
    ) -> None:
        # In federated mode, records are stored directly in instance stores
        store = self._stores.get(instance_id)
        if store:
            await store.store(record)

    async def query(self, query: AuditQuery) -> AuditQueryResult:
        # Determine which stores to query
        if query.instance_id:
            stores_to_query = {
                query.instance_id: self._stores.get(query.instance_id)
            }
            stores_to_query = {k: v for k, v in stores_to_query.items() if v}
        else:
            stores_to_query = self._stores.copy()

        if not stores_to_query:
            return AuditQueryResult(
                records=[],
                total_count=0,
                query=query,
                instances_queried=[],
            )

        # Query all stores in parallel
        async def query_store(
            instance_id: str, store: AuditStore
        ) -> tuple[str, list[AuditRecord], str | None]:
            try:
                records = await asyncio.wait_for(
                    store.query(
                        tenant_id=query.tenant_id,
                        principal_id=query.principal_id,
                        tool_name=query.tool_name,
                        start_time=query.start_time,
                        end_time=query.end_time,
                        # Request more than needed for proper merging
                        limit=query.limit + query.offset,
                        offset=0,
                    ),
                    timeout=self._timeout,
                )
                return instance_id, records, None
            except asyncio.TimeoutError:
                return instance_id, [], "timeout"
            except Exception as e:
                return instance_id, [], str(e)

        results = await asyncio.gather(
            *[query_store(iid, store) for iid, store in stores_to_query.items()]
        )

        # Merge results
        all_records: list[AuditRecord] = []
        errors: dict[str, str] = {}
        instances_queried: list[str] = []

        for instance_id, records, error in results:
            instances_queried.append(instance_id)
            if error:
                errors[instance_id] = error
            else:
                # Apply additional filters not supported by store.query
                for record in records:
                    if query.errors_only and record.error is None:
                        continue
                    if query.model:
                        if record.inputs.get("model") != query.model:
                            continue
                    all_records.append(record)

        # Sort merged results
        reverse = query.sort_desc
        if query.sort_by == "timestamp":
            all_records.sort(key=lambda x: x.timestamp, reverse=reverse)
        elif query.sort_by == "duration_ms":
            all_records.sort(key=lambda x: x.duration_ms or 0, reverse=reverse)

        total_count = len(all_records)

        # Apply pagination
        paginated = all_records[query.offset : query.offset + query.limit]

        return AuditQueryResult(
            records=paginated,
            total_count=total_count,
            query=query,
            instances_queried=instances_queried,
            errors=errors,
        )

    async def get_stats(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        instance_id: str | None = None,
    ) -> AuditStats:
        if start_time is None:
            start_time = datetime.utcnow() - timedelta(hours=1)
        if end_time is None:
            end_time = datetime.utcnow()

        # Query all records in time range
        query_result = await self.query(
            AuditQuery(
                instance_id=instance_id,
                start_time=start_time,
                end_time=end_time,
                limit=1000,  # Get as many as possible for stats (max allowed)
            )
        )

        records = query_result.records

        if not records:
            return AuditStats(start_time=start_time, end_time=end_time)

        # Compute stats (same logic as InMemoryAuditAggregator)
        calls_by_tool: dict[str, int] = {}
        calls_by_model: dict[str, int] = {}
        calls_by_instance: dict[str, int] = {}
        errors_by_type: dict[str, int] = {}
        latencies: list[float] = []
        total_rows = 0

        for record in records:
            calls_by_tool[record.tool_name] = (
                calls_by_tool.get(record.tool_name, 0) + 1
            )

            model = record.inputs.get("model")
            if model:
                calls_by_model[model] = calls_by_model.get(model, 0) + 1

            if record.error:
                error_type = record.error.type
                errors_by_type[error_type] = errors_by_type.get(error_type, 0) + 1

            if record.duration_ms is not None:
                latencies.append(record.duration_ms)

            if record.row_count is not None:
                total_rows += record.row_count

        latencies.sort()
        n = len(latencies)

        def percentile(p: float) -> float:
            if not latencies:
                return 0.0
            idx = int(n * p / 100)
            return latencies[min(idx, n - 1)]

        return AuditStats(
            start_time=start_time,
            end_time=end_time,
            total_calls=len(records),
            calls_by_tool=calls_by_tool,
            calls_by_model=calls_by_model,
            calls_by_instance=calls_by_instance,
            total_errors=sum(errors_by_type.values()),
            errors_by_type=errors_by_type,
            avg_latency_ms=statistics.mean(latencies) if latencies else 0.0,
            p50_latency_ms=percentile(50),
            p95_latency_ms=percentile(95),
            p99_latency_ms=percentile(99),
            total_rows_returned=total_rows,
            avg_rows_per_query=total_rows / len(records) if records else 0.0,
        )

    async def get_recent(
        self,
        limit: int = 50,
        instance_id: str | None = None,
    ) -> list[AuditRecord]:
        result = await self.query(
            AuditQuery(
                instance_id=instance_id,
                limit=limit,
                sort_by="timestamp",
                sort_desc=True,
            )
        )
        return result.records
