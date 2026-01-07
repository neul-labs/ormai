"""
Replay engine for re-executing recorded tool calls.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ormai.core.context import Principal, RunContext
from ormai.eval.recorder import RecordedCall


@dataclass
class ReplayResult:
    """Result of replaying a single call."""

    # Original recorded call
    original: RecordedCall

    # Replay results
    success: bool = True
    outputs: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    duration_ms: float = 0.0

    # Comparison
    outputs_match: bool = True
    differences: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "original_id": self.original.id,
            "success": self.success,
            "outputs_match": self.outputs_match,
            "differences": self.differences,
            "duration_ms": self.duration_ms,
        }


class ReplayEngine:
    """
    Replays recorded tool calls to verify behavior.

    Supports:
    - Exact replay: verify outputs match exactly
    - Policy simulation: test calls against different policies
    - Invariant checking: verify custom assertions hold

    Usage:
        engine = ReplayEngine()
        results = await engine.replay_all(
            calls=recorded_calls,
            executor=my_tool_executor,
        )

        for result in results:
            assert result.outputs_match
    """

    def __init__(
        self,
        comparator: Callable[[Any, Any], bool] | None = None,
    ) -> None:
        """
        Initialize the replay engine.

        Args:
            comparator: Optional custom comparison function for outputs
        """
        self.comparator = comparator or self._default_compare

    async def replay_call(
        self,
        call: RecordedCall,
        executor: Callable[[str, RunContext, dict[str, Any]], Any],
        ctx_factory: Callable[[RecordedCall], RunContext] | None = None,
    ) -> ReplayResult:
        """
        Replay a single recorded call.

        Args:
            call: The recorded call to replay
            executor: Async function that executes the tool
            ctx_factory: Optional factory to create RunContext from call

        Returns:
            ReplayResult with comparison of original vs replay
        """
        import time

        # Create context
        ctx = ctx_factory(call) if ctx_factory else self._create_context(call)

        result = ReplayResult(original=call)
        start = time.perf_counter()

        try:
            # Execute the call
            output = await executor(call.tool_name, ctx, call.inputs)
            result.outputs = output if isinstance(output, dict) else output.model_dump() if hasattr(output, "model_dump") else {"result": output}
            result.success = True

        except Exception as e:
            result.success = False
            result.error = {
                "type": type(e).__name__,
                "message": str(e),
            }

        result.duration_ms = (time.perf_counter() - start) * 1000

        # Compare outputs
        result.outputs_match, result.differences = self._compare_outputs(
            call, result
        )

        return result

    async def replay_all(
        self,
        calls: list[RecordedCall],
        executor: Callable[[str, RunContext, dict[str, Any]], Any],
        ctx_factory: Callable[[RecordedCall], RunContext] | None = None,
        stop_on_mismatch: bool = False,
    ) -> list[ReplayResult]:
        """
        Replay multiple recorded calls.

        Args:
            calls: List of calls to replay
            executor: Async function that executes tools
            ctx_factory: Optional factory to create RunContext
            stop_on_mismatch: Stop on first mismatch if True

        Returns:
            List of ReplayResults
        """
        results = []

        for call in calls:
            result = await self.replay_call(call, executor, ctx_factory)
            results.append(result)

            if stop_on_mismatch and not result.outputs_match:
                break

        return results

    def _create_context(self, call: RecordedCall) -> RunContext:
        """Create a RunContext from a recorded call."""
        return RunContext(
            principal=Principal(
                tenant_id=call.tenant_id,
                user_id=call.principal_id,
                roles=call.roles,
            ),
            request_id=f"replay-{call.id}",
            now=datetime.now(timezone.utc),
            db=None,  # Replay doesn't have real DB
        )

    def _compare_outputs(
        self,
        call: RecordedCall,
        result: ReplayResult,
    ) -> tuple[bool, list[str]]:
        """Compare original and replay outputs."""
        differences = []

        # Check error state
        if call.error is not None and result.error is None:
            differences.append("Original had error, replay succeeded")
        elif call.error is None and result.error is not None:
            differences.append(f"Original succeeded, replay had error: {result.error}")

        # Compare outputs if both succeeded
        if call.outputs is not None and result.outputs is not None and not self.comparator(call.outputs, result.outputs):
            differences.append("Output values differ")

        return len(differences) == 0, differences

    def _default_compare(self, original: Any, replay: Any) -> bool:
        """Default comparison: exact match."""
        return original == replay


class DeterminismChecker:
    """
    Checks that tool calls produce deterministic outputs.

    Runs each call multiple times and verifies outputs match.
    """

    def __init__(self, runs: int = 3) -> None:
        """
        Initialize the checker.

        Args:
            runs: Number of times to run each call
        """
        self.runs = runs

    async def check_call(
        self,
        call: RecordedCall,
        executor: Callable[[str, RunContext, dict[str, Any]], Any],
        ctx_factory: Callable[[RecordedCall], RunContext] | None = None,
    ) -> tuple[bool, list[dict[str, Any]]]:
        """
        Check if a call produces deterministic output.

        Returns:
            Tuple of (is_deterministic, list of outputs from each run)
        """
        engine = ReplayEngine()
        outputs = []

        for _ in range(self.runs):
            result = await engine.replay_call(call, executor, ctx_factory)
            outputs.append(result.outputs)

        # Check all outputs match the first
        is_deterministic = all(o == outputs[0] for o in outputs)
        return is_deterministic, outputs
