"""Tests for the rich query cost model."""

import pytest

from ormai.core.dsl import FilterClause, IncludeClause, OrderClause, QueryRequest
from ormai.policy.costs import (
    CostBreakdown,
    CostBudget,
    CostCategory,
    CostTracker,
    QueryCostEstimator,
    TableStats,
)


class TestCostBreakdown:
    """Tests for CostBreakdown."""

    def test_total_calculation(self):
        """Test total cost calculation."""
        breakdown = CostBreakdown(
            scan_cost=10.0,
            filter_cost=5.0,
            join_cost=20.0,
            sort_cost=3.0,
            aggregate_cost=2.0,
            network_cost=1.0,
            memory_cost=0.5,
        )

        assert breakdown.total == 41.5

    def test_to_dict(self):
        """Test conversion to dictionary."""
        breakdown = CostBreakdown(
            scan_cost=10.0,
            filter_cost=5.0,
            details={"test": "value"},
        )

        result = breakdown.to_dict()

        assert result["scan"] == 10.0
        assert result["filter"] == 5.0
        assert result["total"] == 15.0
        assert result["details"] == {"test": "value"}


class TestTableStats:
    """Tests for TableStats."""

    def test_default_values(self):
        """Test default statistics values."""
        stats = TableStats(table_name="users")

        assert stats.estimated_row_count == 1000
        assert stats.avg_row_size_bytes == 100
        assert stats.indexed_columns == []
        assert stats.default_selectivity == 0.1

    def test_custom_values(self):
        """Test custom statistics."""
        stats = TableStats(
            table_name="large_table",
            estimated_row_count=1_000_000,
            avg_row_size_bytes=500,
            indexed_columns=["id", "email"],
            primary_key="id",
        )

        assert stats.estimated_row_count == 1_000_000
        assert stats.indexed_columns == ["id", "email"]
        assert stats.primary_key == "id"


class TestQueryCostEstimator:
    """Tests for QueryCostEstimator."""

    @pytest.fixture
    def estimator(self):
        """Create an estimator with sample table stats."""
        stats = {
            "Customer": TableStats(
                table_name="Customer",
                estimated_row_count=10000,
                indexed_columns=["email", "tenant_id"],
                primary_key="id",
            ),
            "Order": TableStats(
                table_name="Order",
                estimated_row_count=50000,
                indexed_columns=["customer_id", "created_at"],
                primary_key="id",
            ),
        }
        return QueryCostEstimator(table_stats=stats)

    def test_simple_query_cost(self, estimator):
        """Test cost estimation for a simple query."""
        request = QueryRequest(
            model="Customer",
            select=["id", "name", "email"],
            take=10,
        )

        breakdown = estimator.estimate(request)

        assert breakdown.total > 0
        assert breakdown.scan_cost > 0
        assert breakdown.network_cost > 0
        assert breakdown.details["estimated_base_rows"] == 10000

    def test_filtered_query_reduces_rows(self, estimator):
        """Test that filters reduce estimated rows."""
        request = QueryRequest(
            model="Customer",
            select=["id", "name"],
            where=[FilterClause(field="email", op="eq", value="test@test.com")],
            take=10,
        )

        breakdown = estimator.estimate(request)

        # Filtering on indexed column should reduce estimated rows significantly
        assert breakdown.details["estimated_filtered_rows"] < 10000

    def test_include_adds_join_cost(self, estimator):
        """Test that includes add join cost."""
        request_without_include = QueryRequest(
            model="Customer",
            select=["id", "name"],
            take=10,
        )

        request_with_include = QueryRequest(
            model="Customer",
            select=["id", "name"],
            include=[IncludeClause(relation="orders")],
            take=10,
        )

        cost_without = estimator.estimate(request_without_include)
        cost_with = estimator.estimate(request_with_include)

        assert cost_with.join_cost > cost_without.join_cost
        assert cost_with.total > cost_without.total

    def test_ordering_adds_sort_cost(self, estimator):
        """Test that ordering adds sort cost."""
        request_without_order = QueryRequest(
            model="Customer",
            select=["id", "name"],
            take=10,
        )

        request_with_order = QueryRequest(
            model="Customer",
            select=["id", "name"],
            order_by=[
                OrderClause(field="name", direction="asc"),
                OrderClause(field="created_at", direction="desc"),
            ],
            take=10,
        )

        cost_without = estimator.estimate(request_without_order)
        cost_with = estimator.estimate(request_with_order)

        assert cost_with.sort_cost > cost_without.sort_cost

    def test_string_filter_more_expensive(self, estimator):
        """Test that string filters cost more than equality."""
        request_eq = QueryRequest(
            model="Customer",
            select=["id"],
            where=[FilterClause(field="name", op="eq", value="John")],
            take=10,
        )

        request_contains = QueryRequest(
            model="Customer",
            select=["id"],
            where=[FilterClause(field="name", op="contains", value="John")],
            take=10,
        )

        cost_eq = estimator.estimate(request_eq)
        cost_contains = estimator.estimate(request_contains)

        assert cost_contains.filter_cost > cost_eq.filter_cost

    def test_in_filter_scales_with_items(self, estimator):
        """Test that IN filter cost scales with number of items."""
        request_small = QueryRequest(
            model="Customer",
            select=["id"],
            where=[FilterClause(field="id", op="in", value=[1, 2])],
            take=10,
        )

        request_large = QueryRequest(
            model="Customer",
            select=["id"],
            where=[FilterClause(field="id", op="in", value=list(range(100)))],
            take=10,
        )

        cost_small = estimator.estimate(request_small)
        cost_large = estimator.estimate(request_large)

        assert cost_large.filter_cost > cost_small.filter_cost

    def test_unknown_table_uses_defaults(self):
        """Test that unknown tables use default stats."""
        estimator = QueryCostEstimator()  # No table stats

        request = QueryRequest(
            model="UnknownTable",
            select=["id"],
            take=10,
        )

        breakdown = estimator.estimate(request)

        assert breakdown.total > 0
        assert breakdown.details["estimated_base_rows"] == 1000  # Default

    def test_aggregate_cost_estimation(self, estimator):
        """Test aggregate query cost estimation."""
        breakdown = estimator.estimate_aggregate(
            model="Customer",
            operation="count",
        )

        assert breakdown.scan_cost > 0
        assert breakdown.aggregate_cost > 0
        assert breakdown.details["operation"] == "count"

    def test_aggregate_with_group_by(self, estimator):
        """Test that GROUP BY adds cost."""
        breakdown_no_group = estimator.estimate_aggregate(
            model="Customer",
            operation="count",
        )

        breakdown_with_group = estimator.estimate_aggregate(
            model="Customer",
            operation="count",
            group_by=["status", "country"],
        )

        assert breakdown_with_group.aggregate_cost > breakdown_no_group.aggregate_cost


class TestCostBudget:
    """Tests for CostBudget."""

    def test_within_budget(self):
        """Test that within-budget query passes."""
        budget = CostBudget(max_total_cost=100.0)

        breakdown = CostBreakdown(
            scan_cost=20.0,
            filter_cost=10.0,
        )

        exceeded = budget.check(breakdown)

        assert exceeded == []

    def test_exceeds_total_budget(self):
        """Test that exceeding total budget is caught."""
        budget = CostBudget(max_total_cost=50.0)

        breakdown = CostBreakdown(
            scan_cost=40.0,
            filter_cost=20.0,
        )

        exceeded = budget.check(breakdown)

        assert len(exceeded) == 1
        assert "total_cost" in exceeded[0]

    def test_exceeds_category_budget(self):
        """Test that exceeding category budgets is caught."""
        budget = CostBudget(
            max_total_cost=1000.0,
            max_join_cost=10.0,
        )

        breakdown = CostBreakdown(
            scan_cost=20.0,
            join_cost=50.0,
        )

        exceeded = budget.check(breakdown)

        assert len(exceeded) == 1
        assert "join_cost" in exceeded[0]

    def test_multiple_exceeded_limits(self):
        """Test that multiple exceeded limits are reported."""
        budget = CostBudget(
            max_total_cost=40.0,  # Total will be 50, exceeds 40
            max_scan_cost=10.0,
            max_join_cost=5.0,
        )

        breakdown = CostBreakdown(
            scan_cost=20.0,
            join_cost=30.0,
        )

        exceeded = budget.check(breakdown)

        assert len(exceeded) == 3  # total, scan, and join


class TestCostTracker:
    """Tests for CostTracker."""

    def test_record_and_stats(self):
        """Test recording and retrieving stats."""
        tracker = CostTracker()

        estimated = CostBreakdown(
            scan_cost=10.0,
            filter_cost=5.0,
            details={"estimated_filtered_rows": 100},
        )

        tracker.record(
            model="Customer",
            estimated=estimated,
            actual_duration_ms=50.0,
            actual_rows=95,
        )

        stats = tracker.get_accuracy_stats()

        assert stats["count"] == 1
        assert "avg_cost_to_duration_ratio" in stats
        assert "avg_row_estimation_error" in stats

    def test_empty_tracker_stats(self):
        """Test stats with no records."""
        tracker = CostTracker()

        stats = tracker.get_accuracy_stats()

        assert stats == {"count": 0}

    def test_clear(self):
        """Test clearing recorded data."""
        tracker = CostTracker()

        estimated = CostBreakdown(scan_cost=10.0)
        tracker.record("Customer", estimated, 50.0, 100)

        assert len(tracker.records) == 1

        tracker.clear()

        assert len(tracker.records) == 0

    def test_multiple_records(self):
        """Test accuracy with multiple records."""
        tracker = CostTracker()

        for i in range(5):
            estimated = CostBreakdown(
                scan_cost=10.0 + i,
                details={"estimated_filtered_rows": 100},
            )
            tracker.record(
                model="Customer",
                estimated=estimated,
                actual_duration_ms=50.0 + i * 10,
                actual_rows=100 + i * 5,
            )

        stats = tracker.get_accuracy_stats()

        assert stats["count"] == 5
        assert stats["min_duration_ms"] == 50.0
        assert stats["max_duration_ms"] == 90.0


class TestCostCategory:
    """Tests for CostCategory enum."""

    def test_categories(self):
        """Test that all expected categories exist."""
        assert CostCategory.SCAN == "scan"
        assert CostCategory.FILTER == "filter"
        assert CostCategory.JOIN == "join"
        assert CostCategory.SORT == "sort"
        assert CostCategory.AGGREGATE == "aggregate"
        assert CostCategory.NETWORK == "network"
        assert CostCategory.MEMORY == "memory"
