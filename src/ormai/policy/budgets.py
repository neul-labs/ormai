"""
Budget enforcement and complexity scoring.

Budgets prevent runaway queries by limiting rows, includes, fields,
and query complexity.
"""

from ormai.core.dsl import FilterClause, IncludeClause, QueryRequest
from ormai.core.errors import QueryBudgetExceededError
from ormai.policy.models import Budget


class ComplexityScorer:
    """
    Scores query complexity based on various factors.

    Higher scores indicate more complex (and potentially expensive) queries.
    """

    # Default weights for complexity factors
    DEFAULT_WEIGHTS = {
        "base": 1,
        "per_field": 1,
        "per_filter": 2,
        "per_include": 10,
        "per_order": 1,
        "string_filter": 3,  # contains, startswith, endswith
        "in_filter": 2,  # per item in IN clause
        "between_filter": 2,
    }

    def __init__(self, weights: dict[str, int] | None = None) -> None:
        self.weights = {**self.DEFAULT_WEIGHTS, **(weights or {})}

    def score(self, request: QueryRequest) -> int:
        """
        Calculate complexity score for a query request.

        Returns an integer score where higher = more complex.
        """
        score = self.weights["base"]

        # Field selection
        if request.select:
            score += len(request.select) * self.weights["per_field"]

        # Filters
        if request.where:
            for f in request.where:
                score += self._score_filter(f)

        # Includes
        if request.include:
            for inc in request.include:
                score += self._score_include(inc)

        # Ordering
        if request.order_by:
            score += len(request.order_by) * self.weights["per_order"]

        return score

    def _score_filter(self, filter_clause: FilterClause) -> int:
        """Score a single filter clause."""
        score = self.weights["per_filter"]

        # String operations are more expensive
        if filter_clause.op in ("contains", "startswith", "endswith"):
            score += self.weights["string_filter"]

        # IN clauses scale with list size
        if filter_clause.op == "in" and isinstance(filter_clause.value, list):
            score += len(filter_clause.value) * self.weights["in_filter"]

        # BETWEEN is slightly more expensive
        if filter_clause.op == "between":
            score += self.weights["between_filter"]

        return score

    def _score_include(self, include: IncludeClause) -> int:
        """Score a single include clause."""
        score = self.weights["per_include"]

        # Fields in the include
        if include.select:
            score += len(include.select) * self.weights["per_field"]

        # Filters in the include
        if include.where:
            for f in include.where:
                score += self._score_filter(f)

        return score


class BudgetEnforcer:
    """
    Enforces budget limits on queries.

    Checks various limits and raises appropriate errors when exceeded.
    """

    def __init__(self, budget: Budget, scorer: ComplexityScorer | None = None) -> None:
        self.budget = budget
        self.scorer = scorer or ComplexityScorer()

    def enforce(self, request: QueryRequest) -> None:
        """
        Enforce all budget limits on a query request.

        Raises QueryBudgetExceededError if any limit is exceeded.
        """
        self._check_row_limit(request)
        self._check_field_limit(request)
        self._check_include_limit(request)
        self._check_complexity(request)

    def _check_row_limit(self, request: QueryRequest) -> None:
        """Check if requested rows exceed limit."""
        if request.take > self.budget.max_rows:
            raise QueryBudgetExceededError(
                budget_type="max_rows",
                limit=self.budget.max_rows,
                requested=request.take,
            )

    def _check_field_limit(self, request: QueryRequest) -> None:
        """Check if selected fields exceed limit."""
        if request.select and len(request.select) > self.budget.max_select_fields:
            raise QueryBudgetExceededError(
                budget_type="max_select_fields",
                limit=self.budget.max_select_fields,
                requested=len(request.select),
            )

    def _check_include_limit(self, request: QueryRequest) -> None:
        """Check if includes exceed depth limit."""
        if request.include and len(request.include) > self.budget.max_includes_depth:
            raise QueryBudgetExceededError(
                budget_type="max_includes_depth",
                limit=self.budget.max_includes_depth,
                requested=len(request.include),
            )

    def _check_complexity(self, request: QueryRequest) -> None:
        """Check if query complexity exceeds limit."""
        score = self.scorer.score(request)
        if score > self.budget.max_complexity_score:
            raise QueryBudgetExceededError(
                budget_type="complexity_score",
                limit=self.budget.max_complexity_score,
                requested=score,
            )

    def get_effective_limit(self, requested: int | None) -> int:
        """
        Get the effective row limit considering budget.

        Returns the minimum of requested limit and budget limit.
        """
        if requested is None:
            return self.budget.max_rows
        return min(requested, self.budget.max_rows)
