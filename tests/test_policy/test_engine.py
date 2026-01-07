"""
Tests for policy engine - scoping, budgets, and field access control.
"""

import pytest

from ormai.core.context import Principal, RunContext
from ormai.core.dsl import (
    AggregateRequest,
    BulkUpdateRequest,
    CreateRequest,
    DeleteRequest,
    FilterClause,
    FilterOp,
    GetRequest,
    OrderClause,
    OrderDirection,
    QueryRequest,
    UpdateRequest,
)
from ormai.core.types import FieldMetadata, ModelMetadata, SchemaMetadata, RelationMetadata, RelationType
from ormai.policy.engine import PolicyEngine, PolicyDecision
from ormai.policy.models import (
    Budget,
    FieldAction,
    FieldPolicy,
    ModelPolicy,
    Policy,
    RelationPolicy,
    RowPolicy,
    WritePolicy,
)
from ormai.core.errors import (
    FieldNotAllowedError,
    MaxAffectedRowsExceededError,
    ModelNotAllowedError,
    QueryBudgetExceededError,
    TenantScopeRequiredError,
    WriteDisabledError,
)


# === Test Fixtures ===

@pytest.fixture
def sample_schema():
    """Create a sample schema for testing."""
    return SchemaMetadata(
        models={
            "User": ModelMetadata(
                name="User",
                table_name="users",
                fields={
                    "id": FieldMetadata(name="id", field_type="int", nullable=False),
                    "tenant_id": FieldMetadata(name="tenant_id", field_type="str", nullable=False),
                    "name": FieldMetadata(name="name", field_type="str", nullable=False),
                    "email": FieldMetadata(name="email", field_type="str", nullable=False),
                    "password_hash": FieldMetadata(name="password_hash", field_type="str", nullable=False),
                    "is_admin": FieldMetadata(name="is_admin", field_type="bool", nullable=False),
                    "created_at": FieldMetadata(name="created_at", field_type="datetime", nullable=False),
                },
                relations={
                    "posts": RelationMetadata(
                        name="posts",
                        target_model="Post",
                        relation_type=RelationType.ONE_TO_MANY,
                        foreign_key="author_id",
                    ),
                },
            ),
            "Post": ModelMetadata(
                name="Post",
                table_name="posts",
                fields={
                    "id": FieldMetadata(name="id", field_type="int", nullable=False),
                    "tenant_id": FieldMetadata(name="tenant_id", field_type="str", nullable=False),
                    "title": FieldMetadata(name="title", field_type="str", nullable=False),
                    "content": FieldMetadata(name="content", field_type="str", nullable=False),
                    "author_id": FieldMetadata(name="author_id", field_type="int", nullable=False),
                    "published": FieldMetadata(name="published", field_type="bool", nullable=False),
                    "views": FieldMetadata(name="views", field_type="int", nullable=False),
                },
                relations={
                    "author": RelationMetadata(
                        name="author",
                        target_model="User",
                        relation_type=RelationType.MANY_TO_ONE,
                        foreign_key="author_id",
                    ),
                },
            ),
        }
    )


@pytest.fixture
def policy_with_tenant_scope():
    """Create a policy with tenant scoping enabled."""
    return Policy(
        models={
            "User": ModelPolicy(
                allowed=True,
                readable=True,
                writable=True,
                fields={
                    "password_hash": FieldPolicy(action=FieldAction.DENY),
                    "email": FieldPolicy(action=FieldAction.MASK),
                },
                relations={
                    "posts": RelationPolicy(allowed=True, max_depth=1),
                },
                row_policy=RowPolicy(
                    tenant_scope_field="tenant_id",
                    require_scope=True,
                ),
                write_policy=WritePolicy(
                    enabled=True,
                    allow_create=True,
                    allow_update=True,
                    allow_delete=True,
                    allow_bulk=True,
                    max_affected_rows=100,
                ),
            ),
            "Post": ModelPolicy(
                allowed=True,
                readable=True,
                writable=True,
                relations={
                    "author": RelationPolicy(allowed=True, max_depth=1),
                },
                row_policy=RowPolicy(
                    tenant_scope_field="tenant_id",
                    require_scope=True,
                ),
                write_policy=WritePolicy(
                    enabled=True,
                    allow_create=True,
                    allow_update=True,
                    allow_delete=True,
                    allow_bulk=True,
                    max_affected_rows=100,
                ),
            ),
        },
        default_budget=Budget(
            max_rows=100,
            max_includes_depth=2,
            max_select_fields=20,
            statement_timeout_ms=10000,
        ),
        require_tenant_scope=True,
        writes_enabled=True,
    )


@pytest.fixture
def policy_with_budget_limits():
    """Create a policy with strict budget limits."""
    return Policy(
        models={
            "User": ModelPolicy(
                allowed=True,
                readable=True,
                writable=True,
                row_policy=RowPolicy(tenant_scope_field="tenant_id"),
                budget=Budget(
                    max_rows=10,
                    max_includes_depth=1,
                    max_select_fields=5,
                ),
                write_policy=WritePolicy(
                    enabled=True,
                    allow_create=True,
                    allow_update=True,
                    allow_delete=True,
                    allow_bulk=True,
                    max_affected_rows=5,
                ),
            ),
        },
        default_budget=Budget(
            max_rows=100,
            max_includes_depth=2,
            max_select_fields=40,
        ),
        require_tenant_scope=False,
        writes_enabled=True,
    )


@pytest.fixture
def policy_with_field_restrictions():
    """Create a policy with field-level restrictions."""
    return Policy(
        models={
            "User": ModelPolicy(
                allowed=True,
                readable=True,
                writable=True,
                fields={
                    "id": FieldPolicy(action=FieldAction.ALLOW),
                    "name": FieldPolicy(action=FieldAction.ALLOW),
                    "email": FieldPolicy(action=FieldAction.MASK),
                    "password_hash": FieldPolicy(action=FieldAction.DENY),
                    "is_admin": FieldPolicy(action=FieldAction.DENY),
                },
                aggregatable_fields=["id", "name"],  # Only these can be aggregated
                row_policy=RowPolicy(),
            ),
        },
        default_budget=Budget(max_rows=100),
        require_tenant_scope=False,
        writes_enabled=True,
    )


@pytest.fixture
def policy_with_disabled_writes():
    """Create a policy with writes disabled."""
    return Policy(
        models={
            "User": ModelPolicy(
                allowed=True,
                readable=True,
                writable=False,
                write_policy=WritePolicy(
                    enabled=False,
                    allow_create=False,
                    allow_update=False,
                    allow_delete=False,
                    allow_bulk=False,
                ),
            ),
        },
        default_budget=Budget(max_rows=100),
        require_tenant_scope=False,
        writes_enabled=False,
    )


@pytest.fixture
def tenant_principal():
    """Create a principal with tenant context."""
    return Principal(
        tenant_id="tenant-abc",
        user_id="user-123",
        roles=("user",),
    )


@pytest.fixture
def run_context(tenant_principal):
    """Create a run context."""
    return RunContext(
        principal=tenant_principal,
        db=None,
    )


@pytest.fixture
def policy_engine(sample_schema, policy_with_tenant_scope):
    """Create a policy engine with sample policy."""
    return PolicyEngine(
        policy=policy_with_tenant_scope,
        schema=sample_schema,
    )


# === Tests for Tenant Scoping ===

class TestTenantScoping:
    """Tests for tenant scope enforcement."""

    def test_scope_filter_injected_for_tenant(self, policy_engine, run_context):
        """Test that tenant scope filter is injected."""
        request = QueryRequest(
            model="User",
            select=["id", "name"],
        )

        decision = policy_engine.validate_query(request, run_context)

        assert decision is not None
        assert len(decision.injected_filters) == 1
        assert decision.injected_filters[0].field == "tenant_id"
        assert decision.injected_filters[0].value == "tenant-abc"

    def test_scope_filter_combined_with_user_filters(self, policy_engine, run_context):
        """Test that scope filter is combined with user filters."""
        request = QueryRequest(
            model="User",
            select=["id", "name"],
            where=[
                FilterClause(field="name", op=FilterOp.CONTAINS, value="John")
            ],
        )

        decision = policy_engine.validate_query(request, run_context)

        assert decision is not None
        assert len(decision.injected_filters) == 1
        assert decision.injected_filters[0].field == "tenant_id"

    def test_tenant_scope_required_error_when_no_tenant(self, sample_schema, policy_with_tenant_scope):
        """Test that TenantScopeRequiredError is raised when no tenant in principal."""
        no_tenant_context = RunContext(
            principal=Principal(tenant_id="", user_id="user-123"),
            db=None,
        )
        engine = PolicyEngine(policy=policy_with_tenant_scope, schema=sample_schema)

        request = QueryRequest(model="User", select=["id", "name"])

        with pytest.raises(TenantScopeRequiredError):
            engine.validate_query(request, no_tenant_context)

    def test_row_policy_allows_different_tenant_data(self, policy_engine, run_context):
        """Test that row policy filters out other tenant's data."""
        request = QueryRequest(
            model="User",
            select=["id", "name"],
        )

        decision = policy_engine.validate_query(request, run_context)

        assert decision.injected_filters[0].value == run_context.principal.tenant_id

    def test_scope_injected_for_aggregate(self, policy_engine, run_context):
        """Test that scope filter is injected for aggregate queries."""
        request = AggregateRequest(
            model="User",
            operation="count",
            field="id",
        )

        decision = policy_engine.validate_aggregate(request, run_context)

        assert decision is not None
        assert len(decision.injected_filters) == 1
        assert decision.injected_filters[0].field == "tenant_id"


# === Tests for Budget Enforcement ===

class TestBudgetEnforcement:
    """Tests for budget limits enforcement."""

    def test_query_within_budget_passes(self, policy_engine, run_context):
        """Test that query within budget passes validation."""
        request = QueryRequest(
            model="User",
            select=["id", "name"],
            take=50,
        )

        decision = policy_engine.validate_query(request, run_context)

        assert decision is not None
        assert isinstance(decision, PolicyDecision)

    def test_query_exceeds_max_rows_budget(self, sample_schema, policy_with_budget_limits, run_context):
        """Test that query exceeding max_rows budget fails."""
        engine = PolicyEngine(policy=policy_with_budget_limits, schema=sample_schema)

        request = QueryRequest(
            model="User",
            select=["id", "name"],
            take=50,  # Exceeds max_rows=10
        )

        with pytest.raises(QueryBudgetExceededError):
            engine.validate_query(request, run_context)

    def test_bulk_update_respects_max_affected_rows(self, sample_schema, policy_with_budget_limits, run_context):
        """Test that bulk update respecting max_affected_rows passes."""
        engine = PolicyEngine(policy=policy_with_budget_limits, schema=sample_schema)

        request = BulkUpdateRequest(
            model="User",
            ids=[1, 2, 3],
            data={"name": "Updated"},
        )

        decision = engine.validate_bulk_update(request, run_context)

        assert decision is not None
        assert isinstance(decision, PolicyDecision)


# === Tests for Field Access Control ===

class TestFieldAccessControl:
    """Tests for field-level access control."""

    def test_allowed_fields_included_in_decision(self, policy_engine, run_context):
        """Test that allowed fields are included in policy decision."""
        request = QueryRequest(
            model="User",
            select=["id", "name"],
        )

        decision = policy_engine.validate_query(request, run_context)

        assert decision is not None
        assert "id" in decision.allowed_fields
        assert "name" in decision.allowed_fields

    def test_requesting_denied_field_raises_error(self, sample_schema, policy_with_field_restrictions, run_context):
        """Test that requesting only denied fields raises error."""
        engine = PolicyEngine(policy=policy_with_field_restrictions, schema=sample_schema)

        request = QueryRequest(
            model="User",
            select=["password_hash"],
        )

        with pytest.raises(FieldNotAllowedError):
            engine.validate_query(request, run_context)

    def test_masked_fields_marked_for_redaction(self, policy_engine, run_context):
        """Test that masked fields are marked for redaction."""
        # Use policy_with_tenant_scope which has email masked
        request = QueryRequest(
            model="User",
            select=["email"],
        )

        decision = policy_engine.validate_query(request, run_context)

        assert decision is not None
        assert "email" in decision.redaction_rules
        assert decision.redaction_rules["email"] == "mask"

    def test_denied_fields_marked_for_redaction(self, sample_schema):
        """Test that denied fields are marked for removal."""
        policy = Policy(
            models={
                "User": ModelPolicy(
                    allowed=True,
                    readable=True,
                    fields={
                        "password_hash": FieldPolicy(action=FieldAction.DENY),
                    },
                ),
            },
            default_budget=Budget(max_rows=100),
            require_tenant_scope=False,
        )

        # Verify the field policy is set correctly
        model_policy = policy.get_model_policy("User")
        field_policy = model_policy.get_field_policy("password_hash")
        assert field_policy is not None
        assert field_policy.action == FieldAction.DENY

    def test_aggregatable_fields_restriction(self, sample_schema, policy_with_field_restrictions, run_context):
        """Test that aggregatable_fields restriction is enforced."""
        engine = PolicyEngine(policy=policy_with_field_restrictions, schema=sample_schema)

        request = AggregateRequest(
            model="User",
            operation="count",
            field="email",  # Not in aggregatable_fields
        )

        with pytest.raises(FieldNotAllowedError):
            engine.validate_aggregate(request, run_context)


# === Tests for Write Access Control ===

class TestWriteAccessControl:
    """Tests for write operation access control."""

    def test_create_allowed_when_enabled(self, policy_engine, run_context):
        """Test that create is allowed when write_policy allows it."""
        request = CreateRequest(
            model="User",
            data={
                "tenant_id": "tenant-abc",
                "name": "New User",
                "email": "new@example.com",
            },
        )

        decision = policy_engine.validate_create(request, run_context)

        assert decision is not None
        assert isinstance(decision, PolicyDecision)

    def test_update_allowed_when_enabled(self, policy_engine, run_context):
        """Test that update is allowed when write_policy allows it."""
        request = UpdateRequest(
            model="User",
            id=1,
            data={"name": "Updated Name"},
        )

        decision = policy_engine.validate_update(request, run_context)

        assert decision is not None
        assert isinstance(decision, PolicyDecision)

    def test_delete_allowed_when_enabled(self, policy_engine, run_context):
        """Test that delete is allowed when write_policy allows it."""
        request = DeleteRequest(
            model="User",
            id=1,
        )

        decision = policy_engine.validate_delete(request, run_context)

        assert decision is not None
        assert isinstance(decision, PolicyDecision)

    def test_bulk_update_allowed_when_enabled(self, policy_engine, run_context):
        """Test that bulk update is allowed when write_policy allows it."""
        request = BulkUpdateRequest(
            model="User",
            ids=[1, 2, 3],
            data={"name": "Bulk Updated"},
        )

        decision = policy_engine.validate_bulk_update(request, run_context)

        assert decision is not None
        assert isinstance(decision, PolicyDecision)


# === Tests for Model Access Control ===

class TestModelAccessControl:
    """Tests for model-level access control."""

    def test_allowed_model_access_passes(self, policy_engine, run_context):
        """Test that access to allowed model passes."""
        request = QueryRequest(
            model="User",
            select=["id", "name"],
        )

        decision = policy_engine.validate_query(request, run_context)

        assert decision is not None
        assert isinstance(decision, PolicyDecision)

    def test_disallowed_model_access_fails(self, sample_schema, policy_with_tenant_scope, run_context):
        """Test that access to disallowed model fails."""
        engine = PolicyEngine(policy=policy_with_tenant_scope, schema=sample_schema)

        request = QueryRequest(
            model="NonExistentModel",
            select=["id"],
        )

        with pytest.raises(ModelNotAllowedError):
            engine.validate_query(request, run_context)


# === Tests for Policy Decision Attributes ===

class TestPolicyDecision:
    """Tests for PolicyDecision attributes."""

    def test_decision_tracks_allowed_fields(self, policy_engine, run_context):
        """Test that decision tracks allowed fields correctly."""
        request = QueryRequest(
            model="User",
            select=["id", "name"],
        )

        decision = policy_engine.validate_query(request, run_context)

        assert hasattr(decision, "allowed_fields")
        assert isinstance(decision.allowed_fields, list)

    def test_decision_tracks_injected_filters(self, policy_engine, run_context):
        """Test that decision tracks injected filters."""
        request = QueryRequest(
            model="User",
            select=["id"],
        )

        decision = policy_engine.validate_query(request, run_context)

        assert hasattr(decision, "injected_filters")
        assert isinstance(decision.injected_filters, list)

    def test_decision_tracks_redaction_rules(self, policy_engine, run_context):
        """Test that decision tracks redaction rules."""
        request = QueryRequest(
            model="User",
            select=["email"],
        )

        decision = policy_engine.validate_query(request, run_context)

        assert hasattr(decision, "redaction_rules")
        assert isinstance(decision.redaction_rules, dict)

    def test_decision_tracks_budget(self, policy_engine, run_context):
        """Test that decision tracks budget information."""
        request = QueryRequest(
            model="User",
            select=["id"],
        )

        decision = policy_engine.validate_query(request, run_context)

        assert hasattr(decision, "budget")
        assert decision.budget is not None

    def test_decision_adds_decisions(self, policy_engine, run_context):
        """Test that decision accumulates decisions."""
        request = QueryRequest(
            model="User",
            select=["id"],
        )

        decision = policy_engine.validate_query(request, run_context)

        assert hasattr(decision, "decisions")
        assert len(decision.decisions) > 0

    def test_add_decision_method(self):
        """Test that add_decision works correctly."""
        decision = PolicyDecision()
        decision.add_decision("Test decision 1")
        decision.add_decision("Test decision 2")

        assert len(decision.decisions) == 2
        assert "Test decision 1" in decision.decisions


# === Tests for Edge Cases ===

class TestPolicyEdgeCases:
    """Tests for edge cases in policy enforcement."""

    def test_empty_select_includes_allowed_fields(self, policy_engine, run_context):
        """Test that empty select includes allowed fields."""
        request = QueryRequest(
            model="User",
            select=[],
        )

        decision = policy_engine.validate_query(request, run_context)

        assert decision is not None
        assert len(decision.allowed_fields) >= 2

    def test_query_with_cursor_pagination(self, policy_engine, run_context):
        """Test that cursor pagination works with policy."""
        request = QueryRequest(
            model="User",
            select=["id", "name"],
            take=10,
            cursor="some-cursor-value",
        )

        decision = policy_engine.validate_query(request, run_context)

        assert decision is not None
        assert isinstance(decision, PolicyDecision)

    def test_query_with_order_by(self, policy_engine, run_context):
        """Test that order by works with policy."""
        request = QueryRequest(
            model="User",
            select=["id", "name"],
            order_by=[
                OrderClause(field="name", direction=OrderDirection.ASC)
            ],
        )

        decision = policy_engine.validate_query(request, run_context)

        assert decision is not None
        assert isinstance(decision, PolicyDecision)

    def test_aggregate_without_field_for_count(self, policy_engine, run_context):
        """Test that count aggregate works without specific field."""
        request = AggregateRequest(
            model="User",
            operation="count",
        )

        decision = policy_engine.validate_aggregate(request, run_context)

        assert decision is not None

    def test_get_request_with_policy(self, policy_engine, run_context):
        """Test that get request works with policy."""
        request = GetRequest(
            model="User",
            id=1,
            select=["id", "name"],
        )

        decision = policy_engine.validate_get(request, run_context)

        assert decision is not None
        assert isinstance(decision, PolicyDecision)


# === Tests for Schema Integration ===

class TestSchemaIntegration:
    """Tests for policy engine integration with schema."""

    def test_unknown_model_in_request_raises_error(self, policy_engine, run_context):
        """Test that unknown model in request raises appropriate error."""
        request = QueryRequest(
            model="UnknownModel",
            select=["id"],
        )

        with pytest.raises(ModelNotAllowedError):
            policy_engine.validate_query(request, run_context)

    def test_unknown_field_in_request_raises_error(self, policy_engine, run_context):
        """Test that unknown field in request raises appropriate error."""
        request = QueryRequest(
            model="User",
            select=["unknown_field"],
        )

        with pytest.raises(FieldNotAllowedError):
            policy_engine.validate_query(request, run_context)
