"""
Tests for the redaction module.
"""

from ormai.policy.models import FieldAction, FieldPolicy, ModelPolicy
from ormai.policy.redaction import Redactor


class TestRedactor:
    def test_allow_field(self):
        policy = ModelPolicy(
            allowed=True,
            readable=True,
            fields={"name": FieldPolicy(action=FieldAction.ALLOW)},
        )
        redactor = Redactor(policy)

        record = {"name": "John Doe", "email": "john@example.com"}
        result = redactor.redact_record(record)

        assert result["name"] == "John Doe"
        assert result["email"] == "john@example.com"

    def test_deny_field(self):
        policy = ModelPolicy(
            allowed=True,
            readable=True,
            fields={"password": FieldPolicy(action=FieldAction.DENY)},
        )
        redactor = Redactor(policy)

        record = {"name": "John", "password": "secret123"}
        result = redactor.redact_record(record)

        assert result["name"] == "John"
        assert result["password"] is None

    def test_mask_email(self):
        policy = ModelPolicy(
            allowed=True,
            readable=True,
            fields={"email": FieldPolicy(action=FieldAction.MASK)},
        )
        redactor = Redactor(policy)

        record = {"email": "john@example.com"}
        result = redactor.redact_record(record)

        assert result["email"] == "j***@example.com"

    def test_mask_phone(self):
        policy = ModelPolicy(
            allowed=True,
            readable=True,
            fields={"phone": FieldPolicy(action=FieldAction.MASK)},
        )
        redactor = Redactor(policy)

        record = {"phone": "+12345678901"}
        result = redactor.redact_record(record)

        # Shows first 2 and last 3, masks the rest
        assert result["phone"] == "+1*******901"

    def test_hash_field(self):
        policy = ModelPolicy(
            allowed=True,
            readable=True,
            fields={"ssn": FieldPolicy(action=FieldAction.HASH)},
        )
        redactor = Redactor(policy)

        record = {"ssn": "123-45-6789"}
        result = redactor.redact_record(record)

        # Should be a SHA256 hash
        assert len(result["ssn"]) == 64
        assert result["ssn"] != "123-45-6789"

    def test_null_values(self):
        policy = ModelPolicy(
            allowed=True,
            readable=True,
            fields={"email": FieldPolicy(action=FieldAction.MASK)},
        )
        redactor = Redactor(policy)

        record = {"email": None}
        result = redactor.redact_record(record)

        assert result["email"] is None
