"""Tests for evaluation harness."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ormai.core.context import Principal, RunContext
from ormai.eval.harness import (
    EvalHarness,
    no_cross_tenant_data,
    no_denied_fields,
    response_within_budget,
)
from ormai.eval.recorder import CallRecorder, RecordedCall
from ormai.eval.replay import ReplayEngine


@pytest.fixture
def sample_context() -> RunContext:
    return RunContext(
        principal=Principal(
            tenant_id="tenant-1",
            user_id="user-1",
            roles=["admin"],
        ),
        request_id="req-123",
        now=datetime.now(timezone.utc),
        db=None,
    )


@pytest.fixture
def sample_call() -> RecordedCall:
    return RecordedCall(
        id="call-1",
        tool_name="db.query",
        principal_id="user-1",
        tenant_id="tenant-1",
        roles=["admin"],
        inputs={"model": "Customer", "take": 10},
        outputs={"data": [{"id": 1, "name": "Alice", "tenant_id": "tenant-1"}]},
    )


class TestCallRecorder:
    """Tests for CallRecorder."""

    def test_record_call(self, sample_context: RunContext):
        """Test recording a call."""
        recorder = CallRecorder()

        with recorder.record_call("db.query", sample_context, {"model": "Customer"}) as call:
            call.outputs = {"data": []}

        assert len(recorder.calls) == 1
        assert recorder.calls[0].tool_name == "db.query"
        assert recorder.calls[0].outputs == {"data": []}
        assert recorder.calls[0].duration_ms > 0

    def test_record_error(self, sample_context: RunContext):
        """Test recording a call that raises an error."""
        recorder = CallRecorder()

        with pytest.raises(ValueError), recorder.record_call(
            "db.query", sample_context, {"model": "Customer"}
        ):
            raise ValueError("Test error")

        assert len(recorder.calls) == 1
        assert recorder.calls[0].error is not None
        assert recorder.calls[0].error["type"] == "ValueError"

    def test_save_and_load(self, sample_context: RunContext):
        """Test saving and loading recordings."""
        recorder = CallRecorder()

        with recorder.record_call("db.query", sample_context, {"model": "A"}) as call:
            call.outputs = {"data": [1, 2, 3]}

        with recorder.record_call("db.get", sample_context, {"model": "B", "id": 1}) as call:
            call.outputs = {"data": {"id": 1}}

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "recordings.jsonl"
            recorder.save(path)

            loaded = CallRecorder.from_file(path)

            assert len(loaded.calls) == 2
            assert loaded.calls[0].tool_name == "db.query"
            assert loaded.calls[1].tool_name == "db.get"

    def test_filter_by_tool(self, sample_context: RunContext):
        """Test filtering calls by tool name."""
        recorder = CallRecorder()

        with recorder.record_call("db.query", sample_context, {}) as call:
            call.outputs = {}
        with recorder.record_call("db.get", sample_context, {}) as call:
            call.outputs = {}
        with recorder.record_call("db.query", sample_context, {}) as call:
            call.outputs = {}

        query_calls = recorder.filter_by_tool("db.query")
        assert len(query_calls) == 2

    def test_filter_errors(self, sample_context: RunContext):
        """Test filtering error calls."""
        recorder = CallRecorder()

        with recorder.record_call("db.query", sample_context, {}) as call:
            call.outputs = {}

        with pytest.raises(ValueError), recorder.record_call("db.error", sample_context, {}):
            raise ValueError("oops")

        errors = recorder.filter_errors()
        success = recorder.filter_success()

        assert len(errors) == 1
        assert len(success) == 1


class TestReplayEngine:
    """Tests for ReplayEngine."""

    @pytest.mark.asyncio
    async def test_replay_success(self, sample_call: RecordedCall):
        """Test replaying a successful call."""
        engine = ReplayEngine()

        async def executor(_tool_name, _ctx, _inputs):
            return {"data": [{"id": 1, "name": "Alice", "tenant_id": "tenant-1"}]}

        result = await engine.replay_call(sample_call, executor)

        assert result.success
        assert result.outputs_match
        assert len(result.differences) == 0

    @pytest.mark.asyncio
    async def test_replay_output_mismatch(self, sample_call: RecordedCall):
        """Test detecting output mismatch."""
        engine = ReplayEngine()

        async def executor(_tool_name, _ctx, _inputs):
            return {"data": [{"id": 2, "name": "Bob"}]}  # Different output

        result = await engine.replay_call(sample_call, executor)

        assert result.success
        assert not result.outputs_match

    @pytest.mark.asyncio
    async def test_replay_error(self, sample_call: RecordedCall):
        """Test replaying a call that errors."""
        engine = ReplayEngine()

        async def executor(_tool_name, _ctx, _inputs):
            raise ValueError("Replay error")

        result = await engine.replay_call(sample_call, executor)

        assert not result.success
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_replay_all(self, sample_call: RecordedCall):
        """Test replaying multiple calls."""
        engine = ReplayEngine()
        calls = [sample_call, sample_call]

        async def executor(_tool_name, _ctx, _inputs):
            return sample_call.outputs

        results = await engine.replay_all(calls, executor)

        assert len(results) == 2
        assert all(r.outputs_match for r in results)


class TestEvalHarness:
    """Tests for EvalHarness."""

    @pytest.mark.asyncio
    async def test_evaluate_all_pass(self, sample_call: RecordedCall):
        """Test evaluation with all passing calls."""
        harness = EvalHarness()

        async def executor(_tool_name, _ctx, _inputs):
            return sample_call.outputs

        result = await harness.evaluate([sample_call], executor)

        assert result.all_passed
        assert result.passed == 1
        assert result.failed == 0
        assert result.pass_rate == 100.0

    @pytest.mark.asyncio
    async def test_evaluate_with_invariant(self, sample_call: RecordedCall):
        """Test evaluation with invariant checking."""
        harness = EvalHarness()
        harness.add_invariant("always_true", lambda _call, _result: True)

        async def executor(_tool_name, _ctx, _inputs):
            return sample_call.outputs

        result = await harness.evaluate([sample_call], executor)

        assert result.all_passed
        assert len(result.invariant_violations) == 0

    @pytest.mark.asyncio
    async def test_evaluate_invariant_violation(self, sample_call: RecordedCall):
        """Test evaluation with invariant violation."""
        harness = EvalHarness()
        harness.add_invariant("always_fail", lambda _call, _result: False)

        async def executor(_tool_name, _ctx, _inputs):
            return sample_call.outputs

        result = await harness.evaluate([sample_call], executor)

        assert not result.all_passed
        assert len(result.invariant_violations) == 1
        assert result.invariant_violations[0]["invariant"] == "always_fail"


class TestBuiltInInvariants:
    """Tests for built-in invariant functions."""

    def test_no_cross_tenant_data_pass(self, sample_call: RecordedCall):
        """Test no_cross_tenant_data with matching tenant."""
        from ormai.eval.replay import ReplayResult

        result = ReplayResult(
            original=sample_call,
            outputs={"data": [{"id": 1, "tenant_id": "tenant-1"}]},
        )

        assert no_cross_tenant_data(sample_call, result)

    def test_no_cross_tenant_data_fail(self, sample_call: RecordedCall):
        """Test no_cross_tenant_data with wrong tenant."""
        from ormai.eval.replay import ReplayResult

        result = ReplayResult(
            original=sample_call,
            outputs={"data": [{"id": 1, "tenant_id": "tenant-2"}]},  # Wrong tenant
        )

        assert not no_cross_tenant_data(sample_call, result)

    def test_no_denied_fields_pass(self, sample_call: RecordedCall):
        """Test no_denied_fields with clean output."""
        from ormai.eval.replay import ReplayResult

        check = no_denied_fields(["password", "secret"])
        result = ReplayResult(
            original=sample_call,
            outputs={"data": [{"id": 1, "name": "Alice"}]},
        )

        assert check(sample_call, result)

    def test_no_denied_fields_fail(self, sample_call: RecordedCall):
        """Test no_denied_fields with denied field."""
        from ormai.eval.replay import ReplayResult

        check = no_denied_fields(["password", "secret"])
        result = ReplayResult(
            original=sample_call,
            outputs={"data": [{"id": 1, "password": "hash123"}]},
        )

        assert not check(sample_call, result)

    def test_response_within_budget_pass(self, sample_call: RecordedCall):
        """Test response_within_budget with valid count."""
        from ormai.eval.replay import ReplayResult

        check = response_within_budget(max_rows=10)
        result = ReplayResult(
            original=sample_call,
            outputs={"data": [{"id": i} for i in range(5)]},
        )

        assert check(sample_call, result)

    def test_response_within_budget_fail(self, sample_call: RecordedCall):
        """Test response_within_budget with too many rows."""
        from ormai.eval.replay import ReplayResult

        check = response_within_budget(max_rows=10)
        result = ReplayResult(
            original=sample_call,
            outputs={"data": [{"id": i} for i in range(15)]},
        )

        assert not check(sample_call, result)
