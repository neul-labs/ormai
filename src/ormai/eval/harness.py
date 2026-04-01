"""
Evaluation harness for testing OrmAI tool behavior.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ormai.core.context import RunContext
from ormai.eval.recorder import CallRecorder, RecordedCall
from ormai.eval.replay import ReplayEngine, ReplayResult
from ormai.policy.models import Policy


@dataclass
class EvalResult:
    """Result of an evaluation run."""

    # Summary
    total_calls: int = 0
    passed: int = 0
    failed: int = 0

    # Detailed results
    results: list[ReplayResult] = field(default_factory=list)

    # Invariant violations
    invariant_violations: list[dict[str, Any]] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate as percentage."""
        if self.total_calls == 0:
            return 100.0
        return (self.passed / self.total_calls) * 100

    @property
    def all_passed(self) -> bool:
        """Check if all calls passed."""
        return self.failed == 0 and len(self.invariant_violations) == 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_calls": self.total_calls,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": self.pass_rate,
            "invariant_violations": self.invariant_violations,
        }


class EvalHarness:
    """
    Harness for evaluating OrmAI tool behavior.

    Supports:
    - Recording tool calls during execution
    - Replaying calls and comparing outputs
    - Checking invariants (e.g., no cross-tenant data leakage)
    - Policy simulation

    Usage:
        harness = EvalHarness()

        # Add invariants
        harness.add_invariant(
            name="no_cross_tenant_leak",
            check=lambda call, result: call.tenant_id in str(result.outputs)
        )

        # Run evaluation
        result = await harness.evaluate(
            calls=recorded_calls,
            executor=tool_executor,
        )

        assert result.all_passed
    """

    def __init__(self) -> None:
        self._invariants: list[tuple[str, Callable[[RecordedCall, ReplayResult], bool]]] = []
        self._recorder = CallRecorder()
        self._engine = ReplayEngine()

    @property
    def recorder(self) -> CallRecorder:
        """Get the call recorder."""
        return self._recorder

    def add_invariant(
        self,
        name: str,
        check: Callable[[RecordedCall, ReplayResult], bool],
    ) -> None:
        """
        Add an invariant to check during evaluation.

        Args:
            name: Name of the invariant for reporting
            check: Function that returns True if invariant holds
        """
        self._invariants.append((name, check))

    def clear_invariants(self) -> None:
        """Clear all invariants."""
        self._invariants.clear()

    async def evaluate(
        self,
        calls: list[RecordedCall],
        executor: Callable[[str, RunContext, dict[str, Any]], Any],
        ctx_factory: Callable[[RecordedCall], RunContext] | None = None,
    ) -> EvalResult:
        """
        Evaluate tool behavior by replaying calls.

        Args:
            calls: Recorded calls to replay
            executor: Tool executor function
            ctx_factory: Optional context factory

        Returns:
            EvalResult with pass/fail summary
        """
        result = EvalResult(total_calls=len(calls))

        # Replay all calls
        replay_results = await self._engine.replay_all(
            calls=calls,
            executor=executor,
            ctx_factory=ctx_factory,
        )

        result.results = replay_results

        # Check each result
        for replay_result in replay_results:
            # Check outputs match
            if replay_result.outputs_match:
                result.passed += 1
            else:
                result.failed += 1

            # Check invariants
            for name, check in self._invariants:
                try:
                    if not check(replay_result.original, replay_result):
                        result.invariant_violations.append({
                            "invariant": name,
                            "call_id": replay_result.original.id,
                            "tool": replay_result.original.tool_name,
                        })
                except Exception as e:
                    result.invariant_violations.append({
                        "invariant": name,
                        "call_id": replay_result.original.id,
                        "error": str(e),
                    })

        return result

    async def evaluate_with_policy(
        self,
        calls: list[RecordedCall],
        executor: Callable[[str, RunContext, dict[str, Any], Policy], Any],
        policy: Policy,
        ctx_factory: Callable[[RecordedCall], RunContext] | None = None,
    ) -> EvalResult:
        """
        Evaluate calls against a specific policy.

        Useful for testing policy changes before deployment.

        Args:
            calls: Recorded calls to replay
            executor: Tool executor that accepts policy
            policy: Policy to use for evaluation
            ctx_factory: Optional context factory

        Returns:
            EvalResult with pass/fail summary
        """

        async def policy_executor(
            tool_name: str,
            ctx: RunContext,
            inputs: dict[str, Any],
        ) -> Any:
            return await executor(tool_name, ctx, inputs, policy)

        return await self.evaluate(
            calls=calls,
            executor=policy_executor,
            ctx_factory=ctx_factory,
        )


# Pre-built invariants
def no_cross_tenant_data(call: RecordedCall, result: ReplayResult) -> bool:
    """
    Invariant: Results should only contain data for the request's tenant.

    This is a simple check that looks for tenant_id in outputs.
    For production use, implement a more thorough check.
    """
    if result.outputs is None:
        return True

    # Check that data list (if present) only has matching tenant
    data = result.outputs.get("data", [])
    if isinstance(data, list):
        for row in data:
            if isinstance(row, dict) and "tenant_id" in row and row["tenant_id"] != call.tenant_id:
                return False

    return True


def no_denied_fields(denied_fields: list[str]) -> Callable[[RecordedCall, ReplayResult], bool]:
    """
    Create an invariant that checks no denied fields appear in output.

    Args:
        denied_fields: List of field names that should never appear

    Returns:
        Invariant check function
    """

    def check(call: RecordedCall, result: ReplayResult) -> bool:  # noqa: ARG001
        if result.outputs is None:
            return True

        def check_dict(d: dict) -> bool:
            for key in d:
                if key in denied_fields:
                    return False
                if isinstance(d[key], dict):
                    if not check_dict(d[key]):
                        return False
                elif isinstance(d[key], list):
                    for item in d[key]:
                        if isinstance(item, dict) and not check_dict(item):
                            return False
            return True

        return check_dict(result.outputs)

    return check


def response_within_budget(max_rows: int) -> Callable[[RecordedCall, ReplayResult], bool]:
    """
    Create an invariant that checks row counts are within budget.

    Args:
        max_rows: Maximum allowed rows

    Returns:
        Invariant check function
    """

    def check(call: RecordedCall, result: ReplayResult) -> bool:  # noqa: ARG001
        if result.outputs is None:
            return True

        data = result.outputs.get("data", [])
        if isinstance(data, list):
            return len(data) <= max_rows

        return True

    return check
