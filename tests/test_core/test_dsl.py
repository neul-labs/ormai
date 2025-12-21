"""
Tests for the DSL module.
"""

import pytest
from pydantic import ValidationError

from ormai.core.dsl import (
    AggregateRequest,
    FilterClause,
    FilterOp,
    GetRequest,
    IncludeClause,
    OrderClause,
    OrderDirection,
    QueryRequest,
)


class TestFilterClause:
    def test_basic_filter(self):
        f = FilterClause(field="status", op=FilterOp.EQ, value="active")
        assert f.field == "status"
        assert f.op == FilterOp.EQ
        assert f.value == "active"

    def test_filter_from_dict(self):
        f = FilterClause.model_validate({
            "field": "id",
            "op": "in",
            "value": [1, 2, 3],
        })
        assert f.op == FilterOp.IN
        assert f.value == [1, 2, 3]

    def test_empty_field_rejected(self):
        with pytest.raises(ValidationError):
            FilterClause(field="", op=FilterOp.EQ, value="x")

    def test_sql_injection_in_field_rejected(self):
        with pytest.raises(ValidationError):
            FilterClause(field="id; DROP TABLE users", op=FilterOp.EQ, value=1)


class TestQueryRequest:
    def test_basic_query(self):
        q = QueryRequest(model="Order")
        assert q.model == "Order"
        assert q.take == 25  # Default
        assert q.select is None
        assert q.where is None

    def test_full_query(self):
        q = QueryRequest(
            model="Order",
            select=["id", "status", "total"],
            where=[{"field": "status", "op": "eq", "value": "pending"}],
            order_by=[{"field": "created_at", "direction": "desc"}],
            take=10,
            include=[{"relation": "customer"}],
        )
        assert len(q.select) == 3
        assert len(q.where) == 1
        assert len(q.order_by) == 1
        assert q.take == 10
        assert len(q.include) == 1

    def test_take_limits(self):
        # Valid range
        QueryRequest(model="Order", take=1)
        QueryRequest(model="Order", take=100)

        # Invalid
        with pytest.raises(ValidationError):
            QueryRequest(model="Order", take=0)
        with pytest.raises(ValidationError):
            QueryRequest(model="Order", take=101)


class TestGetRequest:
    def test_basic_get(self):
        g = GetRequest(model="Customer", id=123)
        assert g.model == "Customer"
        assert g.id == 123

    def test_get_with_include(self):
        g = GetRequest(
            model="Customer",
            id=1,
            select=["id", "name"],
            include=[{"relation": "orders"}],
        )
        assert g.select == ["id", "name"]
        assert len(g.include) == 1


class TestAggregateRequest:
    def test_count(self):
        a = AggregateRequest(model="Order", operation="count")
        assert a.operation == "count"
        assert a.field is None

    def test_sum(self):
        a = AggregateRequest(model="Order", operation="sum", field="total")
        assert a.operation == "sum"
        assert a.field == "total"

    def test_invalid_operation(self):
        with pytest.raises(ValidationError):
            AggregateRequest(model="Order", operation="invalid")
