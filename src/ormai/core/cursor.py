"""
Cursor-based pagination with stability guarantees.

Provides keyset-based cursors that remain stable under concurrent writes,
unlike offset-based pagination which can skip or duplicate rows.
"""

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class CursorType(str, Enum):
    """Type of cursor implementation."""

    OFFSET = "offset"  # Simple offset (fast but unstable)
    KEYSET = "keyset"  # Keyset pagination (stable)


@dataclass
class CursorData:
    """
    Decoded cursor data.

    Contains the information needed to resume pagination.
    """

    cursor_type: CursorType
    values: dict[str, Any]  # Key field values for keyset, or offset
    direction: str = "forward"  # forward or backward
    checksum: str | None = None  # For validation

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "t": self.cursor_type.value,
            "v": self.values,
            "d": self.direction,
            "c": self.checksum,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CursorData":
        """Create from dictionary."""
        return cls(
            cursor_type=CursorType(data["t"]),
            values=data["v"],
            direction=data.get("d", "forward"),
            checksum=data.get("c"),
        )


class CursorEncoder:
    """
    Encodes and decodes pagination cursors.

    Cursors are opaque strings that encode:
    - For offset pagination: the current offset
    - For keyset pagination: the key field values of the last row

    Keyset pagination provides stability guarantees:
    - No rows are skipped when new rows are inserted
    - No rows are duplicated when rows are deleted
    - Consistent results during concurrent writes
    """

    def __init__(self, secret: str | None = None) -> None:
        """
        Initialize the encoder.

        Args:
            secret: Optional secret for cursor signing (prevents tampering)
        """
        self.secret = secret or "ormai-cursor-default"

    def encode_offset(self, offset: int) -> str:
        """
        Encode an offset-based cursor.

        Simple and fast, but not stable under concurrent writes.
        """
        data = CursorData(
            cursor_type=CursorType.OFFSET,
            values={"offset": offset},
        )
        return self._encode(data)

    def decode_offset(self, cursor: str) -> int:
        """Decode an offset cursor and return the offset."""
        data = self._decode(cursor)
        if data.cursor_type != CursorType.OFFSET:
            raise ValueError("Expected offset cursor")
        return data.values.get("offset", 0)

    def encode_keyset(
        self,
        key_values: dict[str, Any],
        order_fields: list[str],
        direction: str = "forward",
    ) -> str:
        """
        Encode a keyset-based cursor.

        Args:
            key_values: Values of the key fields from the last row
            order_fields: List of fields used for ordering
            direction: Pagination direction (forward or backward)

        Returns:
            Encoded cursor string
        """
        # Ensure we only include the order fields
        values = {k: self._serialize_value(v) for k, v in key_values.items() if k in order_fields}

        data = CursorData(
            cursor_type=CursorType.KEYSET,
            values=values,
            direction=direction,
        )
        return self._encode(data)

    def decode_keyset(self, cursor: str) -> tuple[dict[str, Any], str]:
        """
        Decode a keyset cursor.

        Returns:
            Tuple of (key_values dict, direction)
        """
        data = self._decode(cursor)
        if data.cursor_type != CursorType.KEYSET:
            raise ValueError("Expected keyset cursor")

        # Deserialize values
        values = {k: self._deserialize_value(v) for k, v in data.values.items()}
        return values, data.direction

    def decode(self, cursor: str) -> CursorData:
        """Decode any cursor type."""
        return self._decode(cursor)

    def _encode(self, data: CursorData) -> str:
        """Encode cursor data to string."""
        # Add checksum if secret is set
        if self.secret:
            data.checksum = self._compute_checksum(data.values)

        json_str = json.dumps(data.to_dict(), separators=(",", ":"))
        return base64.urlsafe_b64encode(json_str.encode()).decode()

    def _decode(self, cursor: str) -> CursorData:
        """Decode cursor string to data."""
        try:
            json_str = base64.urlsafe_b64decode(cursor.encode()).decode()
            raw_data = json.loads(json_str)
            data = CursorData.from_dict(raw_data)

            # Verify checksum if present
            if self.secret and data.checksum:
                expected = self._compute_checksum(data.values)
                if data.checksum != expected:
                    raise ValueError("Cursor checksum mismatch")

            return data
        except Exception as e:
            raise ValueError(f"Invalid cursor: {e}") from e

    def _compute_checksum(self, values: dict[str, Any]) -> str:
        """Compute checksum for cursor values."""
        content = json.dumps(values, sort_keys=True) + self.secret
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _serialize_value(self, value: Any) -> Any:
        """Serialize a value for JSON encoding."""
        if isinstance(value, datetime):
            return {"_dt": value.isoformat()}
        return value

    def _deserialize_value(self, value: Any) -> Any:
        """Deserialize a value from JSON."""
        if isinstance(value, dict) and "_dt" in value:
            return datetime.fromisoformat(value["_dt"])
        return value


def build_keyset_condition(
    cursor_values: dict[str, Any],
    order_fields: list[tuple[str, str]],  # List of (field, direction)
    direction: str = "forward",
) -> dict[str, Any]:
    """
    Build a filter condition for keyset pagination.

    For keyset pagination with ORDER BY (a ASC, b DESC), the cursor
    condition for the next page is:
        (a > cursor_a) OR (a = cursor_a AND b < cursor_b)

    This ensures stable pagination even under concurrent writes.

    Args:
        cursor_values: Key field values from cursor
        order_fields: List of (field_name, sort_direction) tuples
        direction: forward or backward

    Returns:
        Filter condition dict for the query DSL
    """
    if not order_fields:
        return {}

    # Build OR conditions
    conditions = []

    for i in range(len(order_fields)):
        and_parts = []

        # Equality conditions for fields before current
        for j in range(i):
            field, _ = order_fields[j]
            if field in cursor_values:
                and_parts.append({
                    "field": field,
                    "op": "eq",
                    "value": cursor_values[field],
                })

        # Comparison condition for current field
        field, sort_dir = order_fields[i]
        if field in cursor_values:
            # Determine operator based on sort direction and pagination direction
            if direction == "forward":
                op = "gt" if sort_dir.lower() == "asc" else "lt"
            else:
                op = "lt" if sort_dir.lower() == "asc" else "gt"

            and_parts.append({
                "field": field,
                "op": op,
                "value": cursor_values[field],
            })

        if and_parts:
            if len(and_parts) == 1:
                conditions.append(and_parts[0])
            else:
                conditions.append({"and": and_parts})

    if not conditions:
        return {}
    if len(conditions) == 1:
        return conditions[0]
    return {"or": conditions}


# Default encoder instance
default_encoder = CursorEncoder()
