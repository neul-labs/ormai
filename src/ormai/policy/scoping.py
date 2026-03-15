"""
Scope injection for row-level security.

The ScopeInjector modifies queries to enforce tenant isolation and ownership
scoping at the database level.
"""

from ormai.core.context import RunContext
from ormai.core.dsl import FilterClause, FilterOp
from ormai.policy.models import RowPolicy


class ScopeInjector:
    """
    Injects scope filters into queries based on row policies and context.

    This ensures that all queries are automatically filtered to only return
    data that the current principal is allowed to see.
    """

    def __init__(self, row_policy: RowPolicy) -> None:
        self.row_policy = row_policy

    def get_scope_filters(self, ctx: RunContext) -> list[FilterClause]:
        """
        Generate scope filters based on the row policy and context.

        Returns a list of FilterClause objects that should be injected
        into the query's WHERE clause.
        """
        filters: list[FilterClause] = []

        # Tenant scope filter
        if self.row_policy.tenant_scope_field and ctx.principal.tenant_id:
            filters.append(
                FilterClause(
                    field=self.row_policy.tenant_scope_field,
                    op=FilterOp.EQ,
                    value=ctx.principal.tenant_id,
                )
            )

        # Ownership scope filter
        if self.row_policy.ownership_scope_field and ctx.principal.user_id:
            filters.append(
                FilterClause(
                    field=self.row_policy.ownership_scope_field,
                    op=FilterOp.EQ,
                    value=ctx.principal.user_id,
                )
            )

        # Soft delete filter
        if self.row_policy.soft_delete_field and not self.row_policy.include_soft_deleted:
            filters.append(
                FilterClause(
                    field=self.row_policy.soft_delete_field,
                    op=FilterOp.IS_NULL,
                    value=True,
                )
            )

        return filters

    def merge_filters(
        self,
        user_filters: list[FilterClause] | None,
        scope_filters: list[FilterClause],
    ) -> list[FilterClause]:
        """
        Merge user-provided filters with scope filters.

        Scope filters are always applied and cannot be overridden by user filters.
        """
        result = list(scope_filters)  # Scope filters first
        if user_filters:
            result.extend(user_filters)
        return result
