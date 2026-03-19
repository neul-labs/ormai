"""Tests for cursor pagination."""

from datetime import datetime

import pytest

from ormai.core.cursor import (
    CursorEncoder,
    CursorType,
    build_keyset_condition,
)


class TestCursorEncoder:
    """Tests for CursorEncoder."""

    def test_encode_decode_offset(self):
        """Test offset cursor encoding and decoding."""
        encoder = CursorEncoder()

        cursor = encoder.encode_offset(100)
        offset = encoder.decode_offset(cursor)

        assert offset == 100

    def test_encode_decode_keyset(self):
        """Test keyset cursor encoding and decoding."""
        encoder = CursorEncoder()

        values = {"id": 42, "created_at": datetime(2024, 1, 15, 10, 30, 0)}
        order_fields = ["id", "created_at"]

        cursor = encoder.encode_keyset(values, order_fields)
        decoded_values, direction = encoder.decode_keyset(cursor)

        assert decoded_values["id"] == 42
        assert decoded_values["created_at"] == datetime(2024, 1, 15, 10, 30, 0)
        assert direction == "forward"

    def test_keyset_cursor_only_includes_order_fields(self):
        """Test that keyset cursor only includes order fields."""
        encoder = CursorEncoder()

        values = {"id": 42, "name": "test", "status": "active"}
        order_fields = ["id"]  # Only id is order field

        cursor = encoder.encode_keyset(values, order_fields)
        decoded_values, _ = encoder.decode_keyset(cursor)

        assert "id" in decoded_values
        assert "name" not in decoded_values
        assert "status" not in decoded_values

    def test_decode_cursor_type(self):
        """Test decoding cursor type."""
        encoder = CursorEncoder()

        offset_cursor = encoder.encode_offset(50)
        keyset_cursor = encoder.encode_keyset({"id": 1}, ["id"])

        assert encoder.decode(offset_cursor).cursor_type == CursorType.OFFSET
        assert encoder.decode(keyset_cursor).cursor_type == CursorType.KEYSET

    def test_backward_direction(self):
        """Test backward pagination direction."""
        encoder = CursorEncoder()

        cursor = encoder.encode_keyset(
            {"id": 100},
            ["id"],
            direction="backward",
        )
        _, direction = encoder.decode_keyset(cursor)

        assert direction == "backward"

    def test_checksum_validation(self):
        """Test that checksum prevents tampering."""
        encoder = CursorEncoder(secret="my-secret")

        cursor = encoder.encode_offset(100)

        # Valid cursor should decode
        assert encoder.decode_offset(cursor) == 100

        # Tampered cursor should fail
        import base64
        import json

        data = json.loads(base64.urlsafe_b64decode(cursor).decode())
        data["v"]["offset"] = 999  # Tamper with value
        tampered = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()

        with pytest.raises(ValueError, match="checksum"):
            encoder.decode(tampered)

    def test_invalid_cursor(self):
        """Test that invalid cursor raises ValueError."""
        encoder = CursorEncoder()

        with pytest.raises(ValueError, match="Invalid cursor"):
            encoder.decode("not-a-valid-cursor")

    def test_wrong_cursor_type(self):
        """Test that wrong cursor type raises ValueError."""
        encoder = CursorEncoder()

        offset_cursor = encoder.encode_offset(50)

        with pytest.raises(ValueError, match="Expected keyset cursor"):
            encoder.decode_keyset(offset_cursor)


class TestBuildKeysetCondition:
    """Tests for build_keyset_condition."""

    def test_single_field_ascending(self):
        """Test keyset condition for single ascending field."""
        condition = build_keyset_condition(
            cursor_values={"id": 100},
            order_fields=[("id", "asc")],
            direction="forward",
        )

        # Should be: id > 100
        assert condition["field"] == "id"
        assert condition["op"] == "gt"
        assert condition["value"] == 100

    def test_single_field_descending(self):
        """Test keyset condition for single descending field."""
        condition = build_keyset_condition(
            cursor_values={"id": 100},
            order_fields=[("id", "desc")],
            direction="forward",
        )

        # Should be: id < 100
        assert condition["field"] == "id"
        assert condition["op"] == "lt"
        assert condition["value"] == 100

    def test_multiple_fields(self):
        """Test keyset condition for multiple fields."""
        condition = build_keyset_condition(
            cursor_values={"created_at": "2024-01-15", "id": 42},
            order_fields=[("created_at", "desc"), ("id", "asc")],
            direction="forward",
        )

        # Should be: (created_at < cursor) OR (created_at = cursor AND id > cursor)
        assert "or" in condition
        assert len(condition["or"]) == 2

    def test_backward_direction(self):
        """Test backward pagination reverses operators."""
        forward = build_keyset_condition(
            cursor_values={"id": 100},
            order_fields=[("id", "asc")],
            direction="forward",
        )

        backward = build_keyset_condition(
            cursor_values={"id": 100},
            order_fields=[("id", "asc")],
            direction="backward",
        )

        # Forward with ASC uses gt, backward with ASC uses lt
        assert forward["op"] == "gt"
        assert backward["op"] == "lt"

    def test_empty_order_fields(self):
        """Test with no order fields."""
        condition = build_keyset_condition(
            cursor_values={"id": 100},
            order_fields=[],
            direction="forward",
        )

        assert condition == {}

    def test_missing_cursor_value(self):
        """Test with missing cursor value for a field."""
        condition = build_keyset_condition(
            cursor_values={"id": 100},  # Missing created_at
            order_fields=[("created_at", "asc"), ("id", "asc")],
            direction="forward",
        )

        # Should only include condition for id
        assert condition["field"] == "id"
        assert condition["op"] == "gt"
