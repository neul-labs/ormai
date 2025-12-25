"""
Rich query cost estimation model.

Provides detailed cost breakdowns for query planning and optimization.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel

from ormai.core.dsl import FilterClause, IncludeClause, OrderClause, QueryRequest


class CostCategory(str, Enum):
    """Categories of query cost."""

    SCAN = "scan"  # Table/index scan cost
    FILTER = "filter"  # Filter evaluation cost
    JOIN = "join"  # Join/include cost
    SORT = "sort"  # Ordering cost
    AGGREGATE = "aggregate"  # Aggregation cost
    NETWORK = "network"  # Data transfer cost
    MEMORY = "memory"  # Memory allocation cost


@dataclass
class CostBreakdown:
    """Detailed cost breakdown by category."""

    scan_cost: float = 0.0
    filter_cost: float = 0.0
    join_cost: float = 0.0
    sort_cost: float = 0.0
    aggregate_cost: float = 0.0
    network_cost: float = 0.0
    memory_cost: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def total(self) -> float:
        """Total estimated cost."""
        return (
            self.scan_cost
            + self.filter_cost
            + self.join_cost
            + self.sort_cost
            + self.aggregate_cost
            + self.network_cost
            + self.memory_cost
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "scan": self.scan_cost,
            "filter": self.filter_cost,
            "join": self.join_cost,
            "sort": self.sort_cost,
            "aggregate": self.aggregate_cost,
            "network": self.network_cost,
            "memory": self.memory_cost,
            "total": self.total,
            "details": self.details,
        }


class TableStats(BaseModel):
    """Statistics about a table for cost estimation."""

    table_name: str
    estimated_row_count: int = 1000
    avg_row_size_bytes: int = 100
    indexed_columns: list[str] = []
    primary_key: str | None = None

    # Selectivity estimates for common operations
    default_selectivity: float = 0.1  # Default filter selectivity
    unique_selectivity: float = 0.001  # Selectivity for unique columns


class QueryCostEstimator:
    """
    Estimates query execution cost based on table statistics and query structure.

    Cost units are abstract but proportional to expected resource usage.
    """

    # Base costs for operations
    COSTS = {
        # Scan costs
        "full_scan_per_row": 1.0,
        "index_scan_per_row": 0.3,
        "pk_lookup": 0.1,
        # Filter costs
        "equality_filter": 0.1,
        "range_filter": 0.2,
        "string_filter": 0.5,  # LIKE, contains, etc.
        "in_filter_per_item": 0.05,
        "complex_filter": 0.3,  # OR, nested
        # Join costs
        "nested_loop_per_row": 2.0,
        "hash_join_per_row": 0.5,
        "include_base": 5.0,
        "include_per_row": 0.2,
        # Sort costs
        "sort_per_row": 0.1,
        "sort_per_column": 1.0,
        "in_memory_sort_threshold": 1000,
        "disk_sort_multiplier": 3.0,
        # Aggregate costs
        "aggregate_per_row": 0.05,
        "distinct_per_row": 0.2,
        "group_by_per_row": 0.15,
        # Network costs (per row)
        "network_per_row": 0.01,
        "network_per_column": 0.001,
        # Memory costs
        "memory_per_row": 0.001,
        "memory_per_column": 0.0001,
    }

    def __init__(
        self,
        table_stats: dict[str, TableStats] | None = None,
        cost_weights: dict[str, float] | None = None,
    ) -> None:
        """
        Initialize estimator.

        Args:
            table_stats: Statistics for tables (by name)
            cost_weights: Optional custom cost weights
        """
        self.table_stats = table_stats or {}
        self.costs = {**self.COSTS, **(cost_weights or {})}

    def estimate(self, request: QueryRequest) -> CostBreakdown:
        """
        Estimate the cost of executing a query.

        Returns a detailed cost breakdown.
        """
        breakdown = CostBreakdown()
        stats = self.table_stats.get(request.model)

        if stats is None:
            # Use default stats if not available
            stats = TableStats(table_name=request.model)

        # Estimate number of rows after filtering
        estimated_rows = self._estimate_filtered_rows(request, stats)

        # Scan cost
        breakdown.scan_cost = self._estimate_scan_cost(request, stats)
        breakdown.details["estimated_base_rows"] = stats.estimated_row_count

        # Filter cost
        breakdown.filter_cost = self._estimate_filter_cost(request, stats)
        breakdown.details["estimated_filtered_rows"] = estimated_rows

        # Join/include cost
        breakdown.join_cost = self._estimate_join_cost(request, stats, estimated_rows)

        # Sort cost
        breakdown.sort_cost = self._estimate_sort_cost(request, estimated_rows)

        # Network cost (data transfer)
        breakdown.network_cost = self._estimate_network_cost(request, estimated_rows)

        # Memory cost
        breakdown.memory_cost = self._estimate_memory_cost(request, estimated_rows)

        return breakdown

    def estimate_aggregate(
        self,
        model: str,
        operation: str,
        field: str | None = None,
        filters: list[FilterClause] | None = None,
        group_by: list[str] | None = None,
    ) -> CostBreakdown:
        """
        Estimate cost of an aggregate query.

        Args:
            model: Model name
            operation: Aggregate operation (count, sum, avg, min, max)
            field: Field to aggregate
            filters: Optional filters
            group_by: Optional grouping columns
        """
        breakdown = CostBreakdown()
        stats = self.table_stats.get(model, TableStats(table_name=model))

        # Scan cost for the base data
        breakdown.scan_cost = (
            stats.estimated_row_count * self.costs["full_scan_per_row"]
        )

        # Filter cost if filters provided
        if filters:
            for f in filters:
                breakdown.filter_cost += self._filter_clause_cost(f)

        # Aggregate cost
        breakdown.aggregate_cost = (
            stats.estimated_row_count * self.costs["aggregate_per_row"]
        )

        # Group by adds significant cost
        if group_by:
            breakdown.aggregate_cost += (
                stats.estimated_row_count
                * len(group_by)
                * self.costs["group_by_per_row"]
            )

        breakdown.details["operation"] = operation
        breakdown.details["field"] = field
        breakdown.details["group_by"] = group_by

        return breakdown

    def _estimate_filtered_rows(
        self, request: QueryRequest, stats: TableStats
    ) -> int:
        """Estimate number of rows after filtering."""
        rows = stats.estimated_row_count

        if not request.where:
            # Apply take limit
            return min(rows, request.take)

        selectivity = 1.0
        for filter_clause in request.where:
            selectivity *= self._filter_selectivity(filter_clause, stats)

        filtered_rows = int(rows * selectivity)
        return min(filtered_rows, request.take)

    def _filter_selectivity(
        self, filter_clause: FilterClause, stats: TableStats
    ) -> float:
        """Estimate filter selectivity (fraction of rows matching)."""
        # Check if filtering on indexed/unique column
        if filter_clause.field in stats.indexed_columns:
            if filter_clause.op == "eq":
                return stats.unique_selectivity
            return stats.default_selectivity * 0.5

        if filter_clause.field == stats.primary_key:
            if filter_clause.op == "eq":
                return 1.0 / max(stats.estimated_row_count, 1)

        # Selectivity by operator
        selectivity_map = {
            "eq": 0.1,
            "ne": 0.9,
            "lt": 0.3,
            "le": 0.35,
            "gt": 0.3,
            "ge": 0.35,
            "in": min(0.1 * len(filter_clause.value), 0.5)
            if isinstance(filter_clause.value, list)
            else 0.1,
            "nin": 0.9,
            "contains": 0.1,
            "startswith": 0.05,
            "endswith": 0.1,
            "isnull": 0.05,
        }

        return selectivity_map.get(filter_clause.op, stats.default_selectivity)

    def _estimate_scan_cost(
        self, request: QueryRequest, stats: TableStats
    ) -> float:
        """Estimate the cost of scanning data."""
        # Check if we can use an index
        can_use_index = False
        if request.where:
            for f in request.where:
                if f.field in stats.indexed_columns or f.field == stats.primary_key:
                    can_use_index = True
                    break

        if can_use_index:
            return stats.estimated_row_count * self.costs["index_scan_per_row"]
        return stats.estimated_row_count * self.costs["full_scan_per_row"]

    def _estimate_filter_cost(
        self, request: QueryRequest, stats: TableStats
    ) -> float:
        """Estimate cost of evaluating filters."""
        if not request.where:
            return 0.0

        cost = 0.0
        for f in request.where:
            cost += self._filter_clause_cost(f)

        # Multiply by estimated rows to evaluate
        return cost * stats.estimated_row_count

    def _filter_clause_cost(self, filter_clause: FilterClause) -> float:
        """Cost of evaluating a single filter clause."""
        op = filter_clause.op

        if op in ("eq", "ne"):
            return self.costs["equality_filter"]
        if op in ("lt", "le", "gt", "ge", "between"):
            return self.costs["range_filter"]
        if op in ("contains", "startswith", "endswith"):
            return self.costs["string_filter"]
        if op == "in":
            items = (
                len(filter_clause.value)
                if isinstance(filter_clause.value, list)
                else 1
            )
            return self.costs["in_filter_per_item"] * items

        return self.costs["complex_filter"]

    def _estimate_join_cost(
        self, request: QueryRequest, stats: TableStats, estimated_rows: int
    ) -> float:
        """Estimate cost of includes/joins."""
        if not request.include:
            return 0.0

        cost = 0.0
        for include in request.include:
            # Base cost for the include
            cost += self.costs["include_base"]

            # Per-row cost for fetching related data
            cost += estimated_rows * self.costs["include_per_row"]

            # Nested includes add more cost
            # Note: Include might have nested fields selected
            if include.select:
                cost += len(include.select) * 0.1

        return cost

    def _estimate_sort_cost(self, request: QueryRequest, estimated_rows: int) -> float:
        """Estimate cost of ordering results."""
        if not request.order_by:
            return 0.0

        base_sort_cost = estimated_rows * self.costs["sort_per_row"]
        column_cost = len(request.order_by) * self.costs["sort_per_column"]

        # Large sorts may spill to disk
        if estimated_rows > self.costs["in_memory_sort_threshold"]:
            base_sort_cost *= self.costs["disk_sort_multiplier"]

        return base_sort_cost + column_cost

    def _estimate_network_cost(
        self, request: QueryRequest, estimated_rows: int
    ) -> float:
        """Estimate cost of transferring results."""
        # Limit to actual rows returned
        rows_returned = min(estimated_rows, request.take)

        # Columns returned
        columns = len(request.select) if request.select else 10  # Assume 10 default

        return (
            rows_returned * self.costs["network_per_row"]
            + rows_returned * columns * self.costs["network_per_column"]
        )

    def _estimate_memory_cost(
        self, request: QueryRequest, estimated_rows: int
    ) -> float:
        """Estimate memory allocation cost."""
        rows_returned = min(estimated_rows, request.take)
        columns = len(request.select) if request.select else 10

        return (
            rows_returned * self.costs["memory_per_row"]
            + rows_returned * columns * self.costs["memory_per_column"]
        )


class CostBudget(BaseModel):
    """
    Budget defined in terms of estimated cost.

    Allows fine-grained control over query costs.
    """

    # Maximum total estimated cost
    max_total_cost: float = 1000.0

    # Per-category limits (optional)
    max_scan_cost: float | None = None
    max_filter_cost: float | None = None
    max_join_cost: float | None = None
    max_sort_cost: float | None = None
    max_aggregate_cost: float | None = None
    max_network_cost: float | None = None
    max_memory_cost: float | None = None

    def check(self, breakdown: CostBreakdown) -> list[str]:
        """
        Check if a cost breakdown exceeds budget limits.

        Returns list of exceeded limits (empty if within budget).
        """
        exceeded = []

        if breakdown.total > self.max_total_cost:
            exceeded.append(
                f"total_cost: {breakdown.total:.1f} > {self.max_total_cost:.1f}"
            )

        if self.max_scan_cost and breakdown.scan_cost > self.max_scan_cost:
            exceeded.append(
                f"scan_cost: {breakdown.scan_cost:.1f} > {self.max_scan_cost:.1f}"
            )

        if self.max_filter_cost and breakdown.filter_cost > self.max_filter_cost:
            exceeded.append(
                f"filter_cost: {breakdown.filter_cost:.1f} > {self.max_filter_cost:.1f}"
            )

        if self.max_join_cost and breakdown.join_cost > self.max_join_cost:
            exceeded.append(
                f"join_cost: {breakdown.join_cost:.1f} > {self.max_join_cost:.1f}"
            )

        if self.max_sort_cost and breakdown.sort_cost > self.max_sort_cost:
            exceeded.append(
                f"sort_cost: {breakdown.sort_cost:.1f} > {self.max_sort_cost:.1f}"
            )

        if self.max_aggregate_cost and breakdown.aggregate_cost > self.max_aggregate_cost:
            exceeded.append(
                f"aggregate_cost: {breakdown.aggregate_cost:.1f} > {self.max_aggregate_cost:.1f}"
            )

        if self.max_network_cost and breakdown.network_cost > self.max_network_cost:
            exceeded.append(
                f"network_cost: {breakdown.network_cost:.1f} > {self.max_network_cost:.1f}"
            )

        if self.max_memory_cost and breakdown.memory_cost > self.max_memory_cost:
            exceeded.append(
                f"memory_cost: {breakdown.memory_cost:.1f} > {self.max_memory_cost:.1f}"
            )

        return exceeded


class CostTracker:
    """
    Tracks actual vs estimated costs for calibration and monitoring.

    Useful for improving cost estimates over time.
    """

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def record(
        self,
        model: str,
        estimated: CostBreakdown,
        actual_duration_ms: float,
        actual_rows: int,
    ) -> None:
        """Record an actual query execution for comparison."""
        self.records.append(
            {
                "model": model,
                "estimated_cost": estimated.total,
                "estimated_rows": estimated.details.get("estimated_filtered_rows", 0),
                "actual_duration_ms": actual_duration_ms,
                "actual_rows": actual_rows,
                "cost_breakdown": estimated.to_dict(),
            }
        )

    def get_accuracy_stats(self) -> dict[str, Any]:
        """
        Calculate accuracy statistics for cost estimates.

        Returns stats comparing estimated vs actual.
        """
        if not self.records:
            return {"count": 0}

        # Calculate correlation between estimated cost and actual duration
        estimated_costs = [r["estimated_cost"] for r in self.records]
        actual_durations = [r["actual_duration_ms"] for r in self.records]

        # Simple ratio analysis
        ratios = [
            actual / max(est, 0.001)
            for est, actual in zip(estimated_costs, actual_durations)
        ]
        avg_ratio = sum(ratios) / len(ratios)

        # Row estimation accuracy
        row_errors = [
            abs(r["estimated_rows"] - r["actual_rows"]) / max(r["actual_rows"], 1)
            for r in self.records
        ]
        avg_row_error = sum(row_errors) / len(row_errors)

        return {
            "count": len(self.records),
            "avg_cost_to_duration_ratio": avg_ratio,
            "avg_row_estimation_error": avg_row_error,
            "min_duration_ms": min(actual_durations),
            "max_duration_ms": max(actual_durations),
            "avg_duration_ms": sum(actual_durations) / len(actual_durations),
        }

    def clear(self) -> None:
        """Clear recorded data."""
        self.records = []
