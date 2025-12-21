"""
Policy evaluation engine.

The PolicyEngine is the central point for policy evaluation. It validates
requests against policies and provides decisions for query compilation.
"""

from ormai.core.context import RunContext
from ormai.core.dsl import (
    AggregateRequest,
    FilterClause,
    GetRequest,
    IncludeClause,
    QueryRequest,
)
from ormai.core.errors import (
    FieldNotAllowedError,
    ModelNotAllowedError,
    QueryBudgetExceededError,
    QueryTooBroadError,
    RelationNotAllowedError,
    TenantScopeRequiredError,
)
from ormai.core.types import SchemaMetadata
from ormai.policy.models import Budget, ModelPolicy, Policy, RowPolicy


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
        model_policy = self._validate_model_access(request.model, readable=True)
        decision.add_decision(f"Model '{request.model}' access validated")

        # 2. Get and validate budget
        budget = self.policy.get_budget(request.model)
        decision.budget = budget
        self._validate_budget(request, budget, model_policy)
        decision.add_decision(f"Budget validated: max_rows={budget.max_rows}")

        # 3. Validate and filter fields
        schema_model = self.schema.get_model(request.model)
        all_fields = list(schema_model.fields.keys()) if schema_model else []

        if request.select:
            decision.allowed_fields = self._validate_fields(
                request.select, request.model, model_policy, all_fields
            )
        else:
            decision.allowed_fields = model_policy.get_allowed_fields(all_fields)
        decision.add_decision(f"Selected {len(decision.allowed_fields)} fields")

        # 4. Validate relations/includes
        if request.include:
            self._validate_includes(request.include, request.model, model_policy, budget)
            decision.add_decision(f"Validated {len(request.include)} includes")

        # 5. Validate and inject scoping
        row_policy = self.policy.get_row_policy(request.model)
        scope_filters = self._validate_and_get_scope_filters(
            request.model, row_policy, ctx, request.where
        )
        decision.injected_filters.extend(scope_filters)
        if scope_filters:
            decision.add_decision(f"Injected {len(scope_filters)} scope filters")

        # 6. Check broad query guard
        if budget.broad_query_guard:
            self._validate_query_breadth(request, budget, scope_filters)
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
        model_policy = self._validate_model_access(request.model, readable=True)
        decision.add_decision(f"Model '{request.model}' access validated")

        # Get budget
        budget = self.policy.get_budget(request.model)
        decision.budget = budget

        # Validate fields
        schema_model = self.schema.get_model(request.model)
        all_fields = list(schema_model.fields.keys()) if schema_model else []

        if request.select:
            decision.allowed_fields = self._validate_fields(
                request.select, request.model, model_policy, all_fields
            )
        else:
            decision.allowed_fields = model_policy.get_allowed_fields(all_fields)

        # Validate includes
        if request.include:
            self._validate_includes(request.include, request.model, model_policy, budget)

        # Inject scope filters
        row_policy = self.policy.get_row_policy(request.model)
        decision.injected_filters = self._validate_and_get_scope_filters(
            request.model, row_policy, ctx, None
        )

        return decision

    def validate_aggregate(
        self,
        request: AggregateRequest,
        ctx: RunContext,
    ) -> PolicyDecision:
        """Validate an aggregation request."""
        decision = PolicyDecision()

        # Validate model access
        model_policy = self._validate_model_access(request.model, readable=True)
        decision.add_decision(f"Model '{request.model}' access validated")

        # Validate operation is allowed
        if request.operation not in model_policy.allowed_aggregations:
            raise FieldNotAllowedError(
                field=f"aggregation:{request.operation}",
                model=request.model,
                allowed_fields=model_policy.allowed_aggregations,
            )

        # Validate field is aggregatable (for non-count operations)
        if request.field and request.operation != "count":
            if model_policy.aggregatable_fields is not None:
                if request.field not in model_policy.aggregatable_fields:
                    raise FieldNotAllowedError(
                        field=request.field,
                        model=request.model,
                        allowed_fields=model_policy.aggregatable_fields,
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
        decision.injected_filters = self._validate_and_get_scope_filters(
            request.model, row_policy, ctx, request.where
        )

        return decision

    def _validate_model_access(
        self,
        model: str,
        readable: bool = False,
        writable: bool = False,
    ) -> ModelPolicy:
        """Validate that a model is accessible."""
        model_policy = self.policy.get_model_policy(model)

        if model_policy is None:
            raise ModelNotAllowedError(
                model=model,
                allowed_models=self.policy.list_allowed_models(),
            )

        if not model_policy.allowed:
            raise ModelNotAllowedError(
                model=model,
                allowed_models=self.policy.list_allowed_models(),
            )

        if readable and not model_policy.readable:
            raise ModelNotAllowedError(
                model=model,
                allowed_models=[
                    m for m, p in self.policy.models.items() if p.allowed and p.readable
                ],
            )

        if writable and not model_policy.writable:
            raise ModelNotAllowedError(
                model=model,
                allowed_models=[
                    m for m, p in self.policy.models.items() if p.allowed and p.writable
                ],
            )

        return model_policy

    def _validate_fields(
        self,
        fields: list[str],
        model: str,
        model_policy: ModelPolicy,
        all_fields: list[str],
    ) -> list[str]:
        """Validate field access and return allowed fields."""
        allowed = []
        for field in fields:
            if field not in all_fields:
                raise FieldNotAllowedError(
                    field=field,
                    model=model,
                    allowed_fields=all_fields,
                )
            if not model_policy.is_field_allowed(field):
                raise FieldNotAllowedError(
                    field=field,
                    model=model,
                    allowed_fields=model_policy.get_allowed_fields(all_fields),
                )
            allowed.append(field)
        return allowed

    def _validate_includes(
        self,
        includes: list[IncludeClause],
        model: str,
        model_policy: ModelPolicy,
        budget: Budget,
    ) -> None:
        """Validate relation includes."""
        if len(includes) > budget.max_includes_depth:
            raise QueryBudgetExceededError(
                budget_type="includes_count",
                limit=budget.max_includes_depth,
                requested=len(includes),
            )

        schema_model = self.schema.get_model(model)
        available_relations = list(schema_model.relations.keys()) if schema_model else []

        for include in includes:
            # Check relation exists
            if schema_model and include.relation not in schema_model.relations:
                raise RelationNotAllowedError(
                    relation=include.relation,
                    model=model,
                    allowed_relations=available_relations,
                )

            # Check relation policy
            relation_policy = model_policy.relations.get(include.relation)
            if relation_policy is None or not relation_policy.allowed:
                allowed_relations = [
                    r for r, p in model_policy.relations.items() if p.allowed
                ]
                raise RelationNotAllowedError(
                    relation=include.relation,
                    model=model,
                    allowed_relations=allowed_relations or available_relations,
                )

    def _validate_and_get_scope_filters(
        self,
        model: str,
        row_policy: RowPolicy,
        ctx: RunContext,
        existing_filters: list[FilterClause] | None,
    ) -> list[FilterClause]:
        """Validate scoping requirements and return scope filters to inject."""
        filters: list[FilterClause] = []

        # Tenant scoping
        if row_policy.tenant_scope_field:
            if self.policy.require_tenant_scope and not ctx.principal.tenant_id:
                raise TenantScopeRequiredError(
                    model=model,
                    scope_field=row_policy.tenant_scope_field,
                )
            if ctx.principal.tenant_id:
                filters.append(
                    FilterClause(
                        field=row_policy.tenant_scope_field,
                        op="eq",
                        value=ctx.principal.tenant_id,
                    )
                )

        # Ownership scoping (if configured)
        if row_policy.ownership_scope_field and ctx.principal.user_id:
            filters.append(
                FilterClause(
                    field=row_policy.ownership_scope_field,
                    op="eq",
                    value=ctx.principal.user_id,
                )
            )

        # Soft delete filter
        if row_policy.soft_delete_field and not row_policy.include_soft_deleted:
            filters.append(
                FilterClause(
                    field=row_policy.soft_delete_field,
                    op="is_null",
                    value=True,
                )
            )

        return filters

    def _validate_budget(
        self,
        request: QueryRequest,
        budget: Budget,
        model_policy: ModelPolicy,
    ) -> None:
        """Validate request against budget limits."""
        # Check row limit
        if request.take > budget.max_rows:
            raise QueryBudgetExceededError(
                budget_type="max_rows",
                limit=budget.max_rows,
                requested=request.take,
            )

        # Check field count
        if request.select and len(request.select) > budget.max_select_fields:
            raise QueryBudgetExceededError(
                budget_type="select_fields",
                limit=budget.max_select_fields,
                requested=len(request.select),
            )

        # Check include depth
        if request.include and len(request.include) > budget.max_includes_depth:
            raise QueryBudgetExceededError(
                budget_type="includes_depth",
                limit=budget.max_includes_depth,
                requested=len(request.include),
            )

    def _validate_query_breadth(
        self,
        request: QueryRequest,
        budget: Budget,
        scope_filters: list[FilterClause],
    ) -> None:
        """Validate that the query isn't too broad (broad query guard)."""
        total_filters = len(scope_filters)
        if request.where:
            total_filters += len(request.where)

        if total_filters < budget.min_filters_for_broad_query:
            raise QueryTooBroadError(
                model=request.model,
                suggestion=f"Add at least {budget.min_filters_for_broad_query} filter(s) to narrow the query",
            )
