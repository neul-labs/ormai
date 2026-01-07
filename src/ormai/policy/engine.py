"""
Policy evaluation engine.

The PolicyEngine is the central point for policy evaluation. It validates
requests against policies and provides decisions for query compilation.
"""

from typing import TYPE_CHECKING

from ormai.core.context import RunContext
from ormai.core.dsl import (
    AggregateRequest,
    BulkUpdateRequest,
    CreateRequest,
    DeleteRequest,
    FilterClause,
    GetRequest,
    IncludeClause,
    QueryRequest,
    UpdateRequest,
)
from ormai.core.errors import (
    FieldNotAllowedError,
    MaxAffectedRowsExceededError,
    ModelNotAllowedError,
    QueryBudgetExceededError,
    QueryTooBroadError,
    RelationNotAllowedError,
    TenantScopeRequiredError,
    ValidationError,
    WriteDisabledError,
)
from ormai.core.types import SchemaMetadata
from ormai.policy.models import Budget, ModelPolicy, Policy, RowPolicy
from ormai.policy.validation import PolicyValidator

if TYPE_CHECKING:
    from ormai.policy.engine import PolicyEngine


class PolicyDecision:
    """
    Result of policy evaluation.

    Contains all decisions made during policy evaluation that need to be
    applied during query compilation or result processing.
    """

    def __init__(self) -> None:
        self.allowed_fields: list[str] = []
        self.injected_filters: list[FilterClause] = []
        self.redaction_rules: dict[str, str] = {}  # field -> action
        self.budget: Budget | None = None
        self.decisions: list[str] = []  # Audit log of decisions made

    def add_decision(self, decision: str) -> None:
        """Add a decision to the audit log."""
        self.decisions.append(decision)


class PolicyEngine:
    """
    Evaluates policies against requests.

    The engine performs:
    1. Model access validation
    2. Field access validation
    3. Relation access validation
    4. Scope requirement validation
    5. Budget validation
    6. Generates policy decisions for query compilation
    """

    def __init__(self, policy: Policy, schema: SchemaMetadata) -> None:
        self.policy = policy
        self.schema = schema
        self._validator = PolicyValidator(policy, schema, self)

    def validate_query(
        self,
        request: QueryRequest,
        ctx: RunContext,
    ) -> PolicyDecision:
        """
        Validate a query request against policies.

        Raises appropriate errors if the request violates any policy.
        Returns a PolicyDecision with all decisions for query compilation.
        """
        decision = PolicyDecision()

        # 1. Validate model access
        model_policy = self._validator.validate_model_access(
            request.model, readable=True
        )
        decision.add_decision(f"Model '{request.model}' access validated")

        # 2. Get and validate budget
        budget = self.policy.get_budget(request.model)
        decision.budget = budget
        self._validator.validate_budget(request, budget, model_policy)
        decision.add_decision(f"Budget validated: max_rows={budget.max_rows}")

        # 3. Validate and filter fields
        schema_model = self.schema.get_model(request.model)
        all_fields = list(schema_model.fields.keys()) if schema_model else []

        if request.select:
            decision.allowed_fields = self._validator.validate_fields(
                request.select, request.model, model_policy, all_fields
            )
        else:
            decision.allowed_fields = model_policy.get_allowed_fields(all_fields)
        decision.add_decision(f"Selected {len(decision.allowed_fields)} fields")

        # 4. Validate relations/includes
        if request.include:
            self._validator.validate_includes(
                request.include, request.model, model_policy, budget
            )
            decision.add_decision(f"Validated {len(request.include)} includes")

        # 5. Validate and inject scoping
        row_policy = self.policy.get_row_policy(request.model)
        scope_filters = self._validator.validate_and_get_scope_filters(
            request.model, row_policy, ctx, request.where
        )
        decision.injected_filters.extend(scope_filters)
        if scope_filters:
            decision.add_decision(f"Injected {len(scope_filters)} scope filters")

        # 6. Check broad query guard
        if budget.broad_query_guard:
            self._validator.validate_query_breadth(request, budget, scope_filters)
            decision.add_decision("Broad query guard passed")

        # 7. Collect redaction rules
        for field in decision.allowed_fields:
            field_policy = model_policy.get_field_policy(field)
            if field_policy.action.value != "allow":
                decision.redaction_rules[field] = field_policy.action.value

        return decision

    def validate_get(
        self,
        request: GetRequest,
        ctx: RunContext,
    ) -> PolicyDecision:
        """Validate a get-by-id request."""
        decision = PolicyDecision()

        # Validate model access
        model_policy = self._validator.validate_model_access(
            request.model, readable=True
        )
        decision.add_decision(f"Model '{request.model}' access validated")

        # Get budget
        budget = self.policy.get_budget(request.model)
        decision.budget = budget

        # Validate fields
        schema_model = self.schema.get_model(request.model)
        all_fields = list(schema_model.fields.keys()) if schema_model else []

        if request.select:
            decision.allowed_fields = self._validator.validate_fields(
                request.select, request.model, model_policy, all_fields
            )
        else:
            decision.allowed_fields = model_policy.get_allowed_fields(all_fields)

        # Inject scope filters
        row_policy = self.policy.get_row_policy(request.model)
        decision.injected_filters = self._validator.validate_and_get_scope_filters(
            request.model, row_policy, ctx, None
        )

        # Collect redaction rules
        for field in decision.allowed_fields:
            field_policy = model_policy.get_field_policy(field)
            if field_policy.action.value != "allow":
                decision.redaction_rules[field] = field_policy.action.value

        return decision

    def validate_aggregate(
        self,
        request: AggregateRequest,
        ctx: RunContext,
    ) -> PolicyDecision:
        """Validate an aggregate request."""
        decision = PolicyDecision()

        # Validate model access
        model_policy = self._validator.validate_model_access(
            request.model, readable=True
        )
        decision.add_decision(f"Model '{request.model}' access validated")

        # Validate field is aggregatable
        if request.field:
            schema_model = self.schema.get_model(request.model)
            all_fields = list(schema_model.fields.keys()) if schema_model else []
            if request.field not in all_fields:
                raise FieldNotAllowedError(
                    field=request.field,
                    model=request.model,
                    allowed_fields=all_fields,
                )
            # Check if field is aggregatable (None means all allowed fields are aggregatable)
            aggregatable = model_policy.aggregatable_fields
            if aggregatable is not None and request.field not in aggregatable:
                raise FieldNotAllowedError(
                    field=request.field,
                    model=request.model,
                    allowed_fields=list(aggregatable),
                )
            # Also check regular field policy
            if not model_policy.is_field_allowed(request.field):
                raise FieldNotAllowedError(
                    field=request.field,
                    model=request.model,
                )

        # Get budget
        decision.budget = self.policy.get_budget(request.model)

        # Inject scope filters
        row_policy = self.policy.get_row_policy(request.model)
        decision.injected_filters = self._validator.validate_and_get_scope_filters(
            request.model, row_policy, ctx, None
        )

        return decision

    def validate_create(
        self,
        request: CreateRequest,
        ctx: RunContext,
    ) -> PolicyDecision:
        """
        Validate a create request against policies.

        Checks:
        - Model is writable
        - Create operation is allowed
        - Required reason is provided if policy requires it
        - Fields being set are writable
        - Tenant scope is auto-injected
        """
        decision = PolicyDecision()

        # Validate model access
        model_policy = self._validator.validate_model_access(
            request.model, writable=True
        )
        decision.add_decision(f"Model '{request.model}' write access validated")

        # Check if create is allowed
        if not model_policy.write_policy.allow_create:
            raise WriteDisabledError(operation="create", model=request.model)

        # Validate fields
        schema_model = self.schema.get_model(request.model)
        all_fields = list(schema_model.fields.keys()) if schema_model else []

        allowed_fields = self._validator.validate_fields(
            list(request.data.keys()), request.model, model_policy, all_fields
        )
        decision.allowed_fields = allowed_fields
        decision.add_decision(f"Validated {len(allowed_fields)} fields for create")

        # Inject scope filters
        row_policy = self.policy.get_row_policy(request.model)
        decision.injected_filters = self._validator.validate_and_get_scope_filters(
            request.model, row_policy, ctx, None
        )
        if decision.injected_filters:
            decision.add_decision(
                f"Injected {len(decision.injected_filters)} scope filters"
            )

        # Collect redaction rules for audit logging
        for field in decision.allowed_fields:
            field_policy = model_policy.get_field_policy(field)
            if field_policy.action.value != "allow":
                decision.redaction_rules[field] = field_policy.action.value

        return decision

    def validate_update(
        self,
        request: UpdateRequest,
        ctx: RunContext,
    ) -> PolicyDecision:
        """Validate an update request."""
        decision = PolicyDecision()

        # Validate model access
        model_policy = self._validator.validate_model_access(
            request.model, writable=True
        )
        decision.add_decision(f"Model '{request.model}' write access validated")

        # Check if update is allowed
        if not model_policy.write_policy.allow_update:
            raise WriteDisabledError(operation="update", model=request.model)

        # Validate fields
        schema_model = self.schema.get_model(request.model)
        all_fields = list(schema_model.fields.keys()) if schema_model else []

        allowed_fields = self._validator.validate_fields(
            list(request.data.keys()), request.model, model_policy, all_fields
        )
        decision.allowed_fields = allowed_fields
        decision.add_decision(f"Validated {len(allowed_fields)} fields for update")

        # Inject scope filters
        row_policy = self.policy.get_row_policy(request.model)
        decision.injected_filters = self._validator.validate_and_get_scope_filters(
            request.model, row_policy, ctx, None
        )

        # Collect redaction rules
        for field in decision.allowed_fields:
            field_policy = model_policy.get_field_policy(field)
            if field_policy.action.value != "allow":
                decision.redaction_rules[field] = field_policy.action.value

        return decision

    def validate_delete(
        self,
        request: DeleteRequest,
        ctx: RunContext,
    ) -> PolicyDecision:
        """Validate a delete request."""
        decision = PolicyDecision()

        # Validate model access
        model_policy = self._validator.validate_model_access(
            request.model, writable=True
        )
        decision.add_decision(f"Model '{request.model}' write access validated")

        # Check if delete is allowed
        if not model_policy.write_policy.allow_delete:
            raise WriteDisabledError(operation="delete", model=request.model)

        # Inject scope filters
        row_policy = self.policy.get_row_policy(request.model)
        decision.injected_filters = self._validator.validate_and_get_scope_filters(
            request.model, row_policy, ctx, None
        )

        return decision

    def validate_bulk_update(
        self,
        request: BulkUpdateRequest,
        ctx: RunContext,
    ) -> PolicyDecision:
        """Validate a bulk update request."""
        decision = PolicyDecision()

        # Validate model access
        model_policy = self._validator.validate_model_access(
            request.model, writable=True
        )
        decision.add_decision(f"Model '{request.model}' write access validated")

        # Check if bulk update is allowed
        if not model_policy.write_policy.allow_bulk:
            raise WriteDisabledError(operation="bulk_update", model=request.model)

        # Check max affected rows
        budget = self.policy.get_budget(request.model)
        decision.budget = budget
        write_policy = model_policy.write_policy

        if len(request.ids) > write_policy.max_affected_rows:
            raise MaxAffectedRowsExceededError(
                limit=write_policy.max_affected_rows,
                requested=len(request.ids),
            )

        # Validate fields
        schema_model = self.schema.get_model(request.model)
        all_fields = list(schema_model.fields.keys()) if schema_model else []

        allowed_fields = self._validator.validate_fields(
            list(request.data.keys()), request.model, model_policy, all_fields
        )
        decision.allowed_fields = allowed_fields

        # Inject scope filters
        row_policy = self.policy.get_row_policy(request.model)
        decision.injected_filters = self._validator.validate_and_get_scope_filters(
            request.model, row_policy, ctx, None
        )

        # Collect redaction rules
        for field in decision.allowed_fields:
            field_policy = model_policy.get_field_policy(field)
            if field_policy.action.value != "allow":
                decision.redaction_rules[field] = field_policy.action.value

        return decision
