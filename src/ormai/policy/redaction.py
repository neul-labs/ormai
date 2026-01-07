"""
Field redaction logic.

The Redactor applies field-level transformations to query results based on
field policies. This includes masking, hashing, and denying field access.
"""

import hashlib
import re
from enum import Enum
from typing import Any

from ormai.policy.models import FieldAction, FieldPolicy, ModelPolicy


def _mask_partial(value: str) -> str:
    """Generic partial masking: show first and last char."""
    if len(value) <= 2:
        return "*" * len(value)
    return value[0] + "*" * (len(value) - 2) + value[-1]


class RedactionStrategy(str, Enum):
    """Built-in redaction strategies."""

    DENY = "deny"  # Remove field entirely
    MASK_EMAIL = "mask_email"  # user@domain.com -> u***@domain.com
    MASK_PHONE = "mask_phone"  # +1234567890 -> +1******890
    MASK_CARD = "mask_card"  # 1234567890123456 -> ****3456
    MASK_PARTIAL = "mask_partial"  # Show first and last chars
    HASH_SHA256 = "hash_sha256"  # SHA256 hash


def _mask_email_impl(email: str) -> str:
    """Mask an email address: user@domain.com -> u***@domain.com"""
    if "@" not in email:
        return _mask_partial(email)
    local, domain = email.rsplit("@", 1)
    if len(local) <= 1:
        return f"{local}***@{domain}"
    return f"{local[0]}***@{domain}"


def _mask_phone_impl(phone: str) -> str:
    """Mask a phone number: +1234567890 -> +1******890"""
    # Keep first 2 and last 3 chars
    if len(phone) <= 5:
        return "*" * len(phone)
    return phone[:2] + "*" * (len(phone) - 5) + phone[-3:]


class Redactor:
    """
    Applies redaction rules to query results.

    Redaction is applied after query execution to ensure sensitive data
    never leaves the server in readable form.
    """

    def __init__(self, model_policy: ModelPolicy) -> None:
        self.model_policy = model_policy

    def redact_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """
        Apply redaction rules to a single record.

        Returns a new dict with redacted values.
        """
        result = {}
        for field, value in record.items():
            field_policy = self.model_policy.get_field_policy(field)
            result[field] = self._redact_value(field, value, field_policy)
        return result

    def redact_records(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply redaction to a list of records."""
        return [self.redact_record(record) for record in records]

    def _redact_value(
        self,
        field: str,  # noqa: ARG002
        value: Any,
        policy: FieldPolicy,
    ) -> Any:
        """Apply redaction to a single value based on policy."""
        if value is None:
            return None

        match policy.action:
            case FieldAction.ALLOW:
                return value
            case FieldAction.DENY:
                return None  # Field is removed
            case FieldAction.MASK:
                return self._apply_mask(value, policy.mask_pattern)
            case FieldAction.HASH:
                return self._apply_hash(value)

        return value

    def _apply_mask(self, value: Any, pattern: str | None) -> str:
        """Apply masking to a value."""
        str_value = str(value)

        if pattern:
            return self._apply_custom_mask(str_value, pattern)

        # Default masking based on value format
        if "@" in str_value:
            return _mask_email_impl(str_value)
        if str_value.replace("+", "").replace("-", "").replace(" ", "").isdigit():
            if len(str_value) > 10:
                return _mask_phone_impl(str_value)
            return _mask_partial(str_value)
        return _mask_partial(str_value)

    def _apply_custom_mask(self, value: str, pattern: str) -> str:
        """Apply a custom mask pattern."""
        # Support patterns like "****{last4}" or "{first2}***{last2}"
        result = pattern

        # Replace {last4}, {last2}, etc.
        last_match = re.search(r"\{last(\d+)\}", pattern)
        if last_match:
            n = int(last_match.group(1))
            result = result.replace(last_match.group(0), value[-n:] if len(value) >= n else value)

        # Replace {first4}, {first2}, etc.
        first_match = re.search(r"\{first(\d+)\}", pattern)
        if first_match:
            n = int(first_match.group(1))
            result = result.replace(first_match.group(0), value[:n] if len(value) >= n else value)

        return result

    def _apply_hash(self, value: Any) -> str:
        """Hash a value using SHA256."""
        str_value = str(value)
        return hashlib.sha256(str_value.encode()).hexdigest()


def mask_value(value: Any, strategy: RedactionStrategy) -> Any:
    """
    Utility function to mask a value using a built-in strategy.

    This can be used for custom redaction outside of the main flow.
    """
    if value is None:
        return None

    str_value = str(value)

    match strategy:
        case RedactionStrategy.DENY:
            return None
        case RedactionStrategy.MASK_EMAIL:
            return _mask_email_impl(str_value)
        case RedactionStrategy.MASK_PHONE:
            return _mask_phone_impl(str_value)
        case RedactionStrategy.MASK_CARD:
            return "*" * (len(str_value) - 4) + str_value[-4:] if len(str_value) > 4 else "****"
        case RedactionStrategy.MASK_PARTIAL:
            return _mask_partial(str_value)
        case RedactionStrategy.HASH_SHA256:
            return hashlib.sha256(str_value.encode()).hexdigest()

    return value


def _mask_email(email: str) -> str:
    """Mask an email address: user@domain.com -> u***@domain.com"""
    return _mask_email_impl(email)


def _mask_phone(phone: str) -> str:
    """Mask a phone number: +1234567890 -> +1******890"""
    return _mask_phone_impl(phone)
