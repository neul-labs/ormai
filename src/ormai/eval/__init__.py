"""
OrmAI Evaluation and Replay Module.

Provides tools for recording, replaying, and evaluating tool calls
to ensure policy compliance and consistent behavior.
"""

from ormai.eval.harness import (
    EvalHarness,
    EvalResult,
    no_cross_tenant_data,
    no_denied_fields,
    response_within_budget,
)
from ormai.eval.recorder import CallRecorder, RecordedCall
from ormai.eval.replay import DeterminismChecker, ReplayEngine, ReplayResult

__all__ = [
    # Recorder
    "CallRecorder",
    "RecordedCall",
    # Replay
    "ReplayEngine",
    "ReplayResult",
    "DeterminismChecker",
    # Harness
    "EvalHarness",
    "EvalResult",
    # Built-in invariants
    "no_cross_tenant_data",
    "no_denied_fields",
    "response_within_budget",
]
