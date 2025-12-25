"""Tests for mutation DSL schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ormai.core.dsl import (
    BulkUpdateRequest,
    BulkUpdateResult,
    CreateRequest,
    CreateResult,
    DeleteRequest,
    DeleteResult,
    UpdateRequest,
    UpdateResult,
)


class TestCreateRequest:
    """Tests for CreateRequest schema."""

    def test_create_request_basic(self):
        """Test basic create request."""
        request = CreateRequest(
            model="Order",
            data={"customer_id": 1, "total": 99.99},
        )
        assert request.model == "Order"
        assert request.data == {"customer_id": 1, "total": 99.99}
        assert request.reason is None

    def test_create_request_with_reason(self):
        """Test create request with reason."""
        request = CreateRequest(
            model="Order",
            data={"customer_id": 1},
            reason="Customer placed order",
        )
        assert request.reason == "Customer placed order"

    def test_create_request_with_return_fields(self):
        """Test create request with return fields."""
        request = CreateRequest(
            model="Order",
            data={"customer_id": 1},
            return_fields=["id", "created_at"],
        )
        assert request.return_fields == ["id", "created_at"]


class TestUpdateRequest:
    """Tests for UpdateRequest schema."""

    def test_update_request_basic(self):
        """Test basic update request."""
        request = UpdateRequest(
            model="Order",
            id=123,
            data={"status": "shipped"},
        )
        assert request.model == "Order"
        assert request.id == 123
        assert request.data == {"status": "shipped"}

    def test_update_request_with_reason(self):
        """Test update request with reason."""
        request = UpdateRequest(
            model="Order",
            id=123,
            data={"status": "shipped"},
            reason="Order shipped by warehouse",
        )
        assert request.reason == "Order shipped by warehouse"


class TestDeleteRequest:
    """Tests for DeleteRequest schema."""

    def test_delete_request_soft_default(self):
        """Test delete request defaults to soft delete."""
        request = DeleteRequest(
            model="Order",
            id=123,
        )
        assert request.hard is False

    def test_delete_request_hard(self):
        """Test delete request with hard delete."""
        request = DeleteRequest(
            model="Order",
            id=123,
            hard=True,
        )
        assert request.hard is True

    def test_delete_request_with_reason(self):
        """Test delete request with reason."""
        request = DeleteRequest(
            model="Order",
            id=123,
            reason="Customer requested cancellation",
        )
        assert request.reason == "Customer requested cancellation"


class TestBulkUpdateRequest:
    """Tests for BulkUpdateRequest schema."""

    def test_bulk_update_request_basic(self):
        """Test basic bulk update request."""
        request = BulkUpdateRequest(
            model="Order",
            ids=[1, 2, 3],
            data={"status": "cancelled"},
        )
        assert request.model == "Order"
        assert request.ids == [1, 2, 3]
        assert request.data == {"status": "cancelled"}

    def test_bulk_update_request_empty_ids_fails(self):
        """Test bulk update with empty ids fails validation."""
        with pytest.raises(ValidationError):
            BulkUpdateRequest(
                model="Order",
                ids=[],
                data={"status": "cancelled"},
            )

    def test_bulk_update_request_max_ids(self):
        """Test bulk update respects max ids limit."""
        # Should fail with more than 100 ids
        with pytest.raises(ValidationError):
            BulkUpdateRequest(
                model="Order",
                ids=list(range(101)),
                data={"status": "cancelled"},
            )


class TestMutationResults:
    """Tests for mutation result schemas."""

    def test_create_result(self):
        """Test CreateResult schema."""
        result = CreateResult(
            data={"id": 1, "name": "Test"},
            id=1,
            success=True,
        )
        assert result.id == 1
        assert result.success is True

    def test_update_result_found(self):
        """Test UpdateResult when record found."""
        result = UpdateResult(
            data={"id": 1, "status": "updated"},
            success=True,
            found=True,
        )
        assert result.found is True

    def test_update_result_not_found(self):
        """Test UpdateResult when record not found."""
        result = UpdateResult(
            data=None,
            success=True,
            found=False,
        )
        assert result.found is False

    def test_delete_result_soft(self):
        """Test DeleteResult for soft delete."""
        result = DeleteResult(
            success=True,
            found=True,
            soft_deleted=True,
        )
        assert result.soft_deleted is True

    def test_delete_result_hard(self):
        """Test DeleteResult for hard delete."""
        result = DeleteResult(
            success=True,
            found=True,
            soft_deleted=False,
        )
        assert result.soft_deleted is False

    def test_bulk_update_result(self):
        """Test BulkUpdateResult schema."""
        result = BulkUpdateResult(
            updated_count=5,
            success=True,
        )
        assert result.updated_count == 5
        assert result.failed_ids == []
