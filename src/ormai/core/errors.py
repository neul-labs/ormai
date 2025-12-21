"""
Error taxonomy for OrmAI.

All OrmAI errors inherit from OrmAIError and include:
- A unique error code for programmatic handling
- A human-readable message
- Optional retry hints for LLM self-correction
"""

from typing import Any


class OrmAIError(Exception):
    """
    Base class for all OrmAI errors.

    Attributes:
        code: Unique error code for programmatic handling
        message: Human-readable error message
        retry_hints: Suggestions for how to fix the error (for LLM self-correction)
        details: Additional error context
    """

    code: str = "ORMAI_ERROR"

    def __init__(
        self,
        message: str,
        *,
        retry_hints: list[str] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.retry_hints = retry_hints or []
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert error to a dictionary for serialization."""
        return {
            "code": self.code,
            "message": self.message,
            "retry_hints": self.retry_hints,
            "details": self.details,
        }


class OrmAccessDeniedError(OrmAIError):
    """Access to ORM operations is denied."""

    code = "ORM_ACCESS_DENIED"


class ModelNotAllowedError(OrmAIError):
    """The requested model is not in the allowlist."""

    code = "MODEL_NOT_ALLOWED"

    def __init__(
        self,
        model: str,
        allowed_models: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        hints = []
        if allowed_models:
            hints.append(f"Allowed models: {', '.join(allowed_models)}")
        super().__init__(
            f"Model '{model}' is not allowed",
            retry_hints=hints,
            details={"model": model, "allowed_models": allowed_models},
            **kwargs,
        )


class FieldNotAllowedError(OrmAIError):
    """The requested field is not in the allowlist or is explicitly denied."""

    code = "FIELD_NOT_ALLOWED"

    def __init__(
        self,
        field: str,
        model: str,
        allowed_fields: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        hints = []
        if allowed_fields:
            hints.append(f"Allowed fields for {model}: {', '.join(allowed_fields[:10])}")
            if allowed_fields and len(allowed_fields) > 10:
                hints[-1] += f" (and {len(allowed_fields) - 10} more)"
        super().__init__(
            f"Field '{field}' is not allowed on model '{model}'",
            retry_hints=hints,
            details={"field": field, "model": model, "allowed_fields": allowed_fields},
            **kwargs,
        )


class RelationNotAllowedError(OrmAIError):
    """The requested relation include is not allowed."""

    code = "RELATION_NOT_ALLOWED"

    def __init__(
        self,
        relation: str,
        model: str,
        allowed_relations: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        hints = []
        if allowed_relations:
            hints.append(f"Allowed relations for {model}: {', '.join(allowed_relations)}")
        super().__init__(
            f"Relation '{relation}' is not allowed on model '{model}'",
            retry_hints=hints,
            details={"relation": relation, "model": model, "allowed_relations": allowed_relations},
            **kwargs,
        )


class TenantScopeRequiredError(OrmAIError):
    """A tenant scope is required but not provided."""

    code = "TENANT_SCOPE_REQUIRED"

    def __init__(
        self,
        model: str,
        scope_field: str | None = None,
        **kwargs: Any,
    ) -> None:
        hints = ["Ensure you are authenticated with a valid tenant context"]
        if scope_field:
            hints.append(f"The model requires scoping on field: {scope_field}")
        super().__init__(
            f"Tenant scope is required for model '{model}'",
            retry_hints=hints,
            details={"model": model, "scope_field": scope_field},
            **kwargs,
        )


class QueryTooBroadError(OrmAIError):
    """The query is too broad (e.g., no filters on a large table)."""

    code = "QUERY_TOO_BROAD"

    def __init__(
        self,
        model: str,
        suggestion: str | None = None,
        **kwargs: Any,
    ) -> None:
        hints = ["Add more specific filters to narrow down the query"]
        if suggestion:
            hints.append(suggestion)
        super().__init__(
            f"Query on model '{model}' is too broad",
            retry_hints=hints,
            details={"model": model},
            **kwargs,
        )


class QueryBudgetExceededError(OrmAIError):
    """The query exceeds budget limits (rows, complexity, timeout, etc.)."""

    code = "QUERY_BUDGET_EXCEEDED"

    def __init__(
        self,
        budget_type: str,
        limit: int | float,
        requested: int | float | None = None,
        **kwargs: Any,
    ) -> None:
        hints = [f"Reduce {budget_type} to at most {limit}"]
        message = f"Query exceeds {budget_type} budget (limit: {limit}"
        if requested is not None:
            message += f", requested: {requested}"
        message += ")"
        super().__init__(
            message,
            retry_hints=hints,
            details={"budget_type": budget_type, "limit": limit, "requested": requested},
            **kwargs,
        )


class WriteDisabledError(OrmAIError):
    """Write operations are disabled."""

    code = "WRITE_DISABLED"

    def __init__(
        self,
        operation: str,
        model: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            f"Write operation '{operation}' is disabled for model '{model}'",
            retry_hints=["Write operations require explicit policy configuration"],
            details={"operation": operation, "model": model},
            **kwargs,
        )


class WriteApprovalRequiredError(OrmAIError):
    """Write operation requires approval before execution."""

    code = "WRITE_APPROVAL_REQUIRED"

    def __init__(
        self,
        operation: str,
        model: str,
        approval_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        hints = ["This write operation requires human approval before it can be executed"]
        if approval_id:
            hints.append(f"Approval ID: {approval_id}")
        super().__init__(
            f"Write operation '{operation}' on model '{model}' requires approval",
            retry_hints=hints,
            details={"operation": operation, "model": model, "approval_id": approval_id},
            **kwargs,
        )


class MaxAffectedRowsExceededError(OrmAIError):
    """The operation would affect more rows than allowed."""

    code = "MAX_AFFECTED_ROWS_EXCEEDED"

    def __init__(
        self,
        operation: str,
        max_rows: int,
        affected_rows: int | None = None,
        **kwargs: Any,
    ) -> None:
        hints = [f"Limit the operation to affect at most {max_rows} rows"]
        message = f"Operation '{operation}' would exceed max affected rows (limit: {max_rows}"
        if affected_rows is not None:
            message += f", would affect: {affected_rows}"
        message += ")"
        super().__init__(
            message,
            retry_hints=hints,
            details={"operation": operation, "max_rows": max_rows, "affected_rows": affected_rows},
            **kwargs,
        )


class ValidationError(OrmAIError):
    """Input validation failed."""

    code = "VALIDATION_ERROR"

    def __init__(
        self,
        message: str,
        field: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            message,
            details={"field": field} if field else {},
            **kwargs,
        )


class NotFoundError(OrmAIError):
    """
    Requested resource was not found.

    Note: When scoping filters remove a record, we return NotFoundError
    rather than revealing that the record exists but is inaccessible.
    This is the "SafeNotFound" behavior.
    """

    code = "NOT_FOUND"

    def __init__(
        self,
        model: str,
        id: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            f"Resource not found: {model} with id '{id}'",
            details={"model": model, "id": id},
            **kwargs,
        )
