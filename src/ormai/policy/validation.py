"""
Policy validation helpers.

Contains helper methods for validating policies against requests.
"""

from typing import TYPE_CHECKING

from ormai.core.context import RunContext
from ormai.core.dsl import (
    FilterClause,
    IncludeClause,
    QueryRequest,
)
from ormai.core.errors import (
    FieldNotAllowedError,
    MaxAffectedRowsExceededError,
    ModelNotAllowedError,
    QueryBudgetExceededError,
    QueryTooBroadError,
    RelationNotAllowedError,
    TenantScopeRequiredError,
)
from ormai.core.types import SchemaMetadata
from ormai.policy.models import Budget, ModelPolicy, Policy, RowPolicy

if TYPE_CHECKING:
    from ormai.policy.engine import PolicyEngine


class PolicyValidator:
    """
    Helper class for policy validation.

    Contains validation methods that check requests against policies.
    """

    def __init__(
        self, policy: Policy, schema: SchemaMetadata, engine: "PolicyEngine"
    ) -> None:
        """Initialize with policy and schema references."""
        self._policy = policy
        self._schema = schema
        self._engine = engine

    def validate_model_access(
        self,
        model: str,
        readable: bool = False,
        writable: bool = False,
    ) -> ModelPolicy:
        """Validate that a model is accessible."""
        model_policy = self._policy.get_model_policy(model)

        if model_policy is None:
            raise ModelNotAllowedError(
                model=model,
                allowed_models=self._policy.list_allowed_models(),
            )

        if not model_policy.allowed:
            raise ModelNotAllowedError(
                model=model,
                allowed_models=self._policy.list_allowed_models(),
            )

        if readable and not model_policy.readable:
            raise ModelNotAllowedError(
                model=model,
                allowed_models=[
                    m for m, p in self._policy.models.items() if p.allowed and p.readable
                ],
            )

        if writable and not model_policy.writable:
            raise ModelNotAllowedError(
                model=model,
                allowed_models=[
                    m for m, p in self._policy.models.items() if p.allowed and p.writable
                ],
            )

        return model_policy

    def validate_fields(
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

    def validate_includes(
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

        schema_model = self._schema.get_model(model)
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

    def validate_and_get_scope_filters(
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
            if self._policy.require_tenant_scope and not ctx.principal.tenant_id:
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

    def validate_budget(
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

    def validate_query_breadth(
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
