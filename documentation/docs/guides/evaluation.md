# Evaluation & Testing Guide

OrmAI includes a comprehensive evaluation and replay framework for testing agent interactions with your database.

## Overview

The eval framework helps you:

- Record and replay tool calls
- Verify determinism across runs
- Check invariants (no cross-tenant data, budget compliance)
- Test policy enforcement
- Benchmark performance

## Recording Tool Calls

### Basic Recording

```python
from ormai.eval import CallRecorder

recorder = CallRecorder()

# Wrap your toolset
recorded_toolset = recorder.wrap(toolset)

# Execute operations (they're now recorded)
await recorded_toolset.query(ctx, model="Order", ...)
await recorded_toolset.get(ctx, model="User", id="u-123")
await recorded_toolset.create(ctx, model="Order", data={...})

# Get recorded calls
calls = recorder.get_calls()
print(f"Recorded {len(calls)} calls")
```

### Call Record Structure

```python
@dataclass
class CallRecord:
    id: str
    timestamp: datetime
    tool_name: str
    inputs: dict
    principal: dict
    result: ToolResult
    execution_time_ms: float
    metadata: dict
```

### Saving Recordings

```python
# Save to file
recorder.save("./recordings/session_001.jsonl")

# Load from file
recorder = CallRecorder.load("./recordings/session_001.jsonl")
```

## Replay Engine

### Basic Replay

```python
from ormai.eval import ReplayEngine

engine = ReplayEngine(toolset)

# Load recorded calls
calls = CallRecorder.load("./recordings/session_001.jsonl").get_calls()

# Replay all calls
results = await engine.replay(calls)

for original, replayed in results:
    print(f"Tool: {original.tool_name}")
    print(f"Original success: {original.result.success}")
    print(f"Replayed success: {replayed.success}")
```

### Replay with Context Override

```python
# Replay as different user
results = await engine.replay(
    calls,
    ctx_override=RunContext(
        principal=Principal(tenant_id="test-tenant", user_id="test-user"),
        db=test_session,
    ),
)
```

## Determinism Checking

### Basic Check

```python
from ormai.eval import DeterminismChecker

checker = DeterminismChecker(toolset)

# Record and replay multiple times
is_deterministic = await checker.check(
    calls,
    num_runs=3,  # Replay 3 times
)

if not is_deterministic:
    print("Non-deterministic behavior detected!")
    for diff in checker.get_diffs():
        print(f"Call {diff.call_id}: {diff.description}")
```

### Comparison Options

```python
checker = DeterminismChecker(
    toolset,
    compare_options={
        "ignore_fields": ["created_at", "updated_at", "id"],
        "ignore_order": True,  # Don't compare row order
        "tolerance": 0.001,    # Float comparison tolerance
    },
)
```

## Invariant Testing

### Built-in Invariants

```python
from ormai.eval import (
    EvalHarness,
    no_cross_tenant_data,
    no_denied_fields,
    response_within_budget,
)

harness = EvalHarness(toolset, policy)

# Test with invariants
result = await harness.run(
    ctx,
    tool="query",
    kwargs={"model": "Order", "limit": 100},
    invariants=[
        no_cross_tenant_data,
        no_denied_fields,
        response_within_budget,
    ],
)

if result.violations:
    for violation in result.violations:
        print(f"Invariant violated: {violation.name}")
        print(f"  Details: {violation.message}")
```

### Custom Invariants

```python
from ormai.eval import Invariant, InvariantResult

class MaxRowsInvariant(Invariant):
    name = "max_rows"

    def __init__(self, max_rows: int):
        self.max_rows = max_rows

    def check(
        self,
        ctx: RunContext,
        tool_name: str,
        inputs: dict,
        result: ToolResult,
    ) -> InvariantResult:
        if result.success and len(result.data.get("rows", [])) > self.max_rows:
            return InvariantResult(
                passed=False,
                message=f"Returned {len(result.data['rows'])} rows, max is {self.max_rows}",
            )
        return InvariantResult(passed=True)

# Use custom invariant
result = await harness.run(
    ctx,
    tool="query",
    kwargs={"model": "Order"},
    invariants=[MaxRowsInvariant(max_rows=50)],
)
```

### Invariant for All Calls

```python
class NoSensitiveDataInvariant(Invariant):
    name = "no_sensitive_data"
    sensitive_fields = ["ssn", "password", "secret"]

    def check(self, ctx, tool_name, inputs, result) -> InvariantResult:
        if not result.success:
            return InvariantResult(passed=True)

        rows = result.data.get("rows", [result.data])

        for row in rows:
            for field in self.sensitive_fields:
                if field in row and row[field] not in [None, "[REDACTED]", "***"]:
                    return InvariantResult(
                        passed=False,
                        message=f"Sensitive field '{field}' exposed in response",
                    )

        return InvariantResult(passed=True)
```

## Eval Harness

### Comprehensive Testing

```python
from ormai.eval import EvalHarness

harness = EvalHarness(
    toolset=toolset,
    policy=policy,
    adapter=adapter,
)

# Run test suite
results = await harness.run_suite([
    # Test queries
    {
        "name": "query_orders",
        "tool": "query",
        "kwargs": {"model": "Order", "limit": 10},
        "invariants": [no_cross_tenant_data],
        "expected": {"success": True, "min_rows": 0},
    },
    # Test forbidden model
    {
        "name": "query_forbidden",
        "tool": "query",
        "kwargs": {"model": "SecretModel"},
        "expected": {"success": False, "error_code": "MODEL_NOT_ALLOWED"},
    },
    # Test write
    {
        "name": "create_order",
        "tool": "create",
        "kwargs": {"model": "Order", "data": {"status": "pending"}},
        "invariants": [no_denied_fields],
        "expected": {"success": True},
    },
])

# Report
print(f"Passed: {results.passed}/{results.total}")
for failure in results.failures:
    print(f"FAILED: {failure.name}")
    print(f"  Reason: {failure.reason}")
```

### Test Fixtures

```python
@harness.fixture
async def sample_orders(ctx):
    """Create sample orders for testing."""
    orders = []
    for i in range(5):
        result = await toolset.create(
            ctx,
            model="Order",
            data={"status": "pending", "total": 1000 * (i + 1)},
        )
        orders.append(result.data)
    return orders

# Use in tests
results = await harness.run_suite([
    {
        "name": "query_with_fixtures",
        "tool": "query",
        "kwargs": {"model": "Order"},
        "fixtures": ["sample_orders"],
        "expected": {"min_rows": 5},
    },
])
```

## Performance Benchmarking

```python
from ormai.eval import Benchmark

benchmark = Benchmark(toolset)

# Benchmark a query
stats = await benchmark.run(
    tool="query",
    kwargs={"model": "Order", "limit": 100},
    iterations=100,
)

print(f"Mean: {stats.mean_ms:.2f}ms")
print(f"P50: {stats.p50_ms:.2f}ms")
print(f"P95: {stats.p95_ms:.2f}ms")
print(f"P99: {stats.p99_ms:.2f}ms")
print(f"Min: {stats.min_ms:.2f}ms")
print(f"Max: {stats.max_ms:.2f}ms")
```

### Comparative Benchmarks

```python
# Compare different configurations
results = await benchmark.compare([
    {
        "name": "limit_10",
        "tool": "query",
        "kwargs": {"model": "Order", "limit": 10},
    },
    {
        "name": "limit_100",
        "tool": "query",
        "kwargs": {"model": "Order", "limit": 100},
    },
    {
        "name": "limit_1000",
        "tool": "query",
        "kwargs": {"model": "Order", "limit": 1000},
    },
])

for name, stats in results.items():
    print(f"{name}: {stats.mean_ms:.2f}ms mean")
```

## Integration with pytest

```python
# tests/test_tools.py
import pytest
from ormai.eval import EvalHarness

@pytest.fixture
async def harness(toolset, policy, adapter):
    return EvalHarness(toolset, policy, adapter)

@pytest.fixture
async def ctx(db_session):
    return RunContext(
        principal=Principal(tenant_id="test", user_id="test-user"),
        db=db_session,
    )

async def test_query_respects_tenant_scope(harness, ctx):
    result = await harness.run(
        ctx,
        tool="query",
        kwargs={"model": "Order"},
        invariants=[no_cross_tenant_data],
    )
    assert not result.violations

async def test_denied_model_rejected(harness, ctx):
    result = await harness.run(
        ctx,
        tool="query",
        kwargs={"model": "SecretModel"},
    )
    assert not result.result.success
    assert "MODEL_NOT_ALLOWED" in str(result.result.error)

async def test_field_masking_applied(harness, ctx):
    result = await harness.run(
        ctx,
        tool="query",
        kwargs={"model": "User", "select": ["email"]},
    )

    for row in result.result.data["rows"]:
        # Email should be masked
        assert "***" in row.get("email", "")
```

## CI/CD Integration

```yaml
# .github/workflows/eval.yml
name: Evaluation Tests
on: [push, pull_request]

jobs:
  eval:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - run: pip install -e .[test]

      - name: Run eval tests
        run: pytest tests/eval/ -v
        env:
          DATABASE_URL: postgres://postgres:test@localhost/test

      - name: Run benchmarks
        run: python -m ormai.eval benchmark --config ./benchmark.yaml

      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: eval-results
          path: ./eval-results/
```

## Best Practices

1. **Record production samples** - Use real query patterns for testing

2. **Test all invariants** - Especially cross-tenant and field policies

3. **Benchmark regularly** - Catch performance regressions

4. **Use fixtures** - Consistent test data

5. **Test edge cases** - Empty results, max limits, errors

6. **Replay across versions** - Ensure backward compatibility

## Next Steps

- [Multi-Tenant Setup](multi-tenant.md) - Test tenant isolation
- [Policies](../concepts/policies.md) - Policy testing
- [Audit Logging](../concepts/audit-logging.md) - Verify audit trails
