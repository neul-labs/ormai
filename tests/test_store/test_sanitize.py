"""
Tests for store sanitization - sensitive data detection and redaction.
"""

import pytest
import re

from ormai.store.sanitize import (
    sanitize_inputs,
    SENSITIVE_PATTERNS,
)


class TestSensitivePatternDetection:
    """Tests for sensitive pattern detection regex."""

    def test_password_detection(self):
        """Test that password fields are detected."""
        assert SENSITIVE_PATTERNS.search("password") is not None
        assert SENSITIVE_PATTERNS.search("pwd") is not None
        assert SENSITIVE_PATTERNS.search("passwd") is not None
        assert SENSITIVE_PATTERNS.search("secret") is not None

    def test_token_detection(self):
        """Test that token fields are detected."""
        assert SENSITIVE_PATTERNS.search("token") is not None
        assert SENSITIVE_PATTERNS.search("access_token") is not None
        assert SENSITIVE_PATTERNS.search("auth_token") is not None
        assert SENSITIVE_PATTERNS.search("bearer") is not None

    def test_api_key_detection(self):
        """Test that API key fields are detected."""
        assert SENSITIVE_PATTERNS.search("api_key") is not None
        assert SENSITIVE_PATTERNS.search("apikey") is not None
        assert SENSITIVE_PATTERNS.search("api_secret") is not None

    def test_credential_detection(self):
        """Test that credential fields are detected."""
        assert SENSITIVE_PATTERNS.search("credential") is not None

    def test_session_detection(self):
        """Test that session fields are detected."""
        assert SENSITIVE_PATTERNS.search("session") is not None
        assert SENSITIVE_PATTERNS.search("session_id") is not None

    def test_case_insensitive(self):
        """Test that pattern matching is case insensitive."""
        assert SENSITIVE_PATTERNS.search("PASSWORD") is not None
        assert SENSITIVE_PATTERNS.search("TOKEN") is not None
        assert SENSITIVE_PATTERNS.search("Secret") is not None

    def test_non_sensitive_fields_not_detected(self):
        """Test that non-sensitive fields are not detected."""
        assert SENSITIVE_PATTERNS.search("username") is None
        assert SENSITIVE_PATTERNS.search("name") is None
        assert SENSITIVE_PATTERNS.search("email") is None
        assert SENSITIVE_PATTERNS.search("address") is None
        assert SENSITIVE_PATTERNS.search("phone") is None


class TestContainsSensitiveField:
    """Tests for sensitive field detection helper."""

    def _contains_sensitive_field(self, field_name: str) -> bool:
        """Helper to check if field name contains sensitive pattern."""
        return SENSITIVE_PATTERNS.search(field_name) is not None

    def test_password_field_detected(self):
        """Test that password field is detected."""
        assert self._contains_sensitive_field("password") is True
        assert self._contains_sensitive_field("password_hash") is True
        assert self._contains_sensitive_field("user_password") is True

    def test_token_field_detected(self):
        """Test that token field is detected."""
        assert self._contains_sensitive_field("token") is True
        assert self._contains_sensitive_field("access_token") is True
        assert self._contains_sensitive_field("auth_token") is True

    def test_api_key_field_detected(self):
        """Test that API key field is detected."""
        assert self._contains_sensitive_field("api_key") is True
        assert self._contains_sensitive_field("apikey") is True
        assert self._contains_sensitive_field("api_secret") is True

    def test_non_sensitive_field_not_detected(self):
        """Test that non-sensitive fields are not detected."""
        assert self._contains_sensitive_field("name") is False
        assert self._contains_sensitive_field("email") is False
        assert self._contains_sensitive_field("address") is False
        assert self._contains_sensitive_field("phone") is False
        assert self._contains_sensitive_field("age") is False
        assert self._contains_sensitive_field("created_at") is False


class TestSanitizeInputs:
    """Tests for sanitize_inputs function."""

    def test_sanitize_removes_password(self):
        """Test that password field is sanitized."""
        data = {"name": "John", "password": "secret123"}
        result = sanitize_inputs(data)

        assert result["password"] == "[REDACTED]"
        assert "name" in result

    def test_sanitize_removes_token(self):
        """Test that token field is sanitized."""
        data = {"token": "abc123", "name": "John"}
        result = sanitize_inputs(data)

        assert result["token"] == "[REDACTED]"
        assert "name" in result

    def test_sanitize_removes_api_key(self):
        """Test that API key field is sanitized."""
        data = {"api_key": "key123", "name": "John"}
        result = sanitize_inputs(data)

        assert result["api_key"] == "[REDACTED]"
        assert "name" in result

    def test_sanitize_handles_empty_dict(self):
        """Test that empty dict is handled."""
        result = sanitize_inputs({})
        assert result == {}

    def test_sanitize_preserves_non_sensitive_fields(self):
        """Test that non-sensitive fields are preserved."""
        data = {
            "name": "John",
            "email": "john@example.com",
            "age": 30,
        }
        result = sanitize_inputs(data)

        assert result["name"] == "John"
        assert result["email"] == "john@example.com"
        assert result["age"] == 30

    def test_sanitize_handles_nested_keys(self):
        """Test that nested field names are checked."""
        data = {"user": {"password": "secret"}}
        result = sanitize_inputs(data)

        # Nested keys are checked and values redacted
        assert result["user"]["password"] == "[REDACTED]"

    def test_sanitize_removes_multiple_sensitive_fields(self):
        """Test that multiple sensitive fields are redacted."""
        data = {
            "password": "secret1",
            "token": "abc123",
            "api_key": "key456",
            "name": "John",
        }
        result = sanitize_inputs(data)

        assert result["password"] == "[REDACTED]"
        assert result["token"] == "[REDACTED]"
        assert result["api_key"] == "[REDACTED]"
        assert "name" in result


class TestSanitizeNestedInputs:
    """Tests for nested sanitization in sanitize_inputs."""

    def test_sanitize_nested_dict(self):
        """Test sanitization of nested dictionaries."""
        data = {
            "user": {
                "name": "John",
                "password": "secret",
            },
            "token": "abc",
        }
        result = sanitize_inputs(data)

        assert result["user"]["password"] == "[REDACTED]"
        assert result["token"] == "[REDACTED]"
        assert result["user"]["name"] == "John"

    def test_sanitize_deeply_nested(self):
        """Test sanitization of deeply nested dictionaries."""
        data = {
            "level1": {
                "level2": {
                    "level3": {
                        "password": "secret",
                        "name": "John",
                    }
                }
            }
        }
        result = sanitize_inputs(data)

        assert result["level1"]["level2"]["level3"]["password"] == "[REDACTED]"
        assert result["level1"]["level2"]["level3"]["name"] == "John"

    def test_sanitize_nested_list(self):
        """Test sanitization of dictionaries in lists."""
        data = {
            "users": [
                {"name": "John", "password": "secret1"},
                {"name": "Jane", "password": "secret2"},
            ]
        }
        result = sanitize_inputs(data)

        assert result["users"][0]["password"] == "[REDACTED]"
        assert result["users"][1]["password"] == "[REDACTED]"
        assert result["users"][0]["name"] == "John"
        assert result["users"][1]["name"] == "Jane"

    def test_sanitize_nested_list_with_dicts(self):
        """Test sanitization of list containing dicts with sensitive fields."""
        data = {
            "records": [
                {"id": 1, "secret_key": "value1"},
                {"id": 2, "secret_key": "value2"},
            ]
        }
        result = sanitize_inputs(data)

        assert result["records"][0]["secret_key"] == "[REDACTED]"
        assert result["records"][1]["secret_key"] == "[REDACTED]"

    def test_sanitize_empty_nested(self):
        """Test handling of empty nested structures."""
        data = {"users": []}
        result = sanitize_inputs(data)
        assert result == {"users": []}

    def test_sanitize_mixed_types(self):
        """Test sanitization with mixed types."""
        data = {
            "string": "value",
            "number": 42,
            "bool": True,
            "null": None,
            "password": "secret",
        }
        result = sanitize_inputs(data)

        assert result["string"] == "value"
        assert result["number"] == 42
        assert result["bool"] is True
        assert result["null"] is None
        assert result["password"] == "[REDACTED]"


class TestSanitizeEdgeCases:
    """Tests for edge cases in sanitization."""

    def test_sanitize_handles_special_characters(self):
        """Test that field names with special chars are handled."""
        # password_123 contains "password", api-key does not contain sensitive pattern
        data = {"password_123": "secret", "api-key": "key"}
        result = sanitize_inputs(data)

        # password_123 contains "password" so it should be redacted
        assert result["password_123"] == "[REDACTED]"
        # api-key does not match sensitive patterns, value preserved
        assert result["api-key"] == "key"

    def test_sanitize_unicode_field_names(self):
        """Test handling of unicode in field names."""
        data = {"password": "secret", "nom": "value"}  # French "nom" is fine
        result = sanitize_inputs(data)

        assert result["password"] == "[REDACTED]"
        assert result["nom"] == "value"

    def test_sanitize_empty_string_field(self):
        """Test handling of empty string field names."""
        data = {"": "value", "password": "secret"}
        result = sanitize_inputs(data)

        assert result["password"] == "[REDACTED]"
        assert result[""] == "value"

    def test_sanitize_very_long_field_name(self):
        """Test handling of very long field names."""
        long_name = "a" * 1000
        data = {long_name: "value", "password": "secret"}
        result = sanitize_inputs(data)

        assert result["password"] == "[REDACTED]"
        assert long_name in result

    def test_sanitize_preserves_numeric_values(self):
        """Test that numeric values are preserved."""
        # Note: user_id and session_id contain sensitive patterns and will be redacted
        data = {"record_id": 123, "count": 456, "name": "John"}
        result = sanitize_inputs(data)

        assert result["record_id"] == 123
        assert result["count"] == 456
        assert result["name"] == "John"


class TestSanitizePatterns:
    """Tests for pattern matching in sanitization."""

    def test_common_password_variants(self):
        """Test detection of common password field variants."""
        variants = [
            "password",
            "Password",
            "PASSWORD",
            "user_password",
            "db_password",
            "admin_password",
        ]
        for variant in variants:
            data = {variant: "secret"}
            result = sanitize_inputs(data)
            assert result[variant] == "[REDACTED]", f"Failed to redact {variant}"

    def test_common_token_variants(self):
        """Test detection of common token field variants."""
        variants = [
            "token",
            "Token",
            "access_token",
            "refresh_token",
            "auth_token",
        ]
        for variant in variants:
            data = {variant: "secret"}
            result = sanitize_inputs(data)
            assert result[variant] == "[REDACTED]", f"Failed to redact {variant}"

    def test_common_api_key_variants(self):
        """Test detection of common API key field variants."""
        variants = [
            "api_key",
            "apikey",
            "api_secret",
            "client_secret",
        ]
        for variant in variants:
            data = {variant: "secret"}
            result = sanitize_inputs(data)
            assert result[variant] == "[REDACTED]", f"Failed to redact {variant}"


class TestSanitizeIntegration:
    """Integration tests for sanitization."""

    def test_sanitize_audit_record(self):
        """Test sanitization of an audit record."""
        record = {
            "action": "query",
            "model": "User",
            "inputs": {
                "name": "John",
                "password": "secret",
                "token": "abc123",
            },
            "outputs": [
                {"id": 1, "email": "john@example.com"},
            ],
            "principal": {
                "tenant_id": "tenant-1",
                "user_id": "user-1",
            },
        }
        result = sanitize_inputs(record)

        # Check inputs are sanitized
        assert result["inputs"]["password"] == "[REDACTED]"
        assert result["inputs"]["token"] == "[REDACTED]"
        assert result["inputs"]["name"] == "John"

    def test_sanitize_with_nested_objects(self):
        """Test sanitization with nested objects."""
        # Note: "auth_data" is used instead of "credentials" (which matches "credential")
        data = {
            "user": {
                "auth_data": {
                    "password": "secret",
                    "totp_secret": "abc",
                },
                "profile": {
                    "name": "John",
                    "email": "john@example.com",
                },
            },
        }
        result = sanitize_inputs(data)

        assert result["user"]["auth_data"]["password"] == "[REDACTED]"
        # totp_secret contains "secret" substring
        assert result["user"]["auth_data"]["totp_secret"] == "[REDACTED]"
        assert result["user"]["profile"]["name"] == "John"
        assert result["user"]["profile"]["email"] == "john@example.com"

    def test_partial_sanitization(self):
        """Test that partial sanitization works correctly."""
        data = {
            "api_key": "key123",
            "session_id": "sess456",
            "request_data": {
                "name": "John",
                "password": "secret",
            },
            "response_data": {
                "user_id": 1,
            },
        }
        result = sanitize_inputs(data)

        # Top-level sensitive fields
        assert result["api_key"] == "[REDACTED]"
        assert result["session_id"] == "[REDACTED]"

        # Nested
        assert result["request_data"]["password"] == "[REDACTED]"
        assert result["request_data"]["name"] == "John"

    def test_sanitize_preserves_structure_after_redaction(self):
        """Test that the structure is preserved after redaction."""
        data = {
            "config": {
                "database": {
                    "host": "localhost",
                    "password": "secret",
                },
                "cache": {
                    "redis_password": "cache_secret",
                },
            },
            "users": [
                {"name": "Alice", "api_token": "token1"},
                {"name": "Bob", "api_token": "token2"},
            ],
        }
        result = sanitize_inputs(data)

        # Check structure is preserved
        assert "config" in result
        assert "database" in result["config"]
        assert "cache" in result["config"]
        assert "users" in result

        # Check redaction
        assert result["config"]["database"]["password"] == "[REDACTED]"
        assert result["config"]["cache"]["redis_password"] == "[REDACTED]"
        assert result["users"][0]["api_token"] == "[REDACTED]"
        assert result["users"][1]["api_token"] == "[REDACTED]"

        # Check non-sensitive values preserved
        assert result["config"]["database"]["host"] == "localhost"
        assert result["users"][0]["name"] == "Alice"
        assert result["users"][1]["name"] == "Bob"
