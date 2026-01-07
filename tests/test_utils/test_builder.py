"""
Tests for the policy builder.
"""

from ormai.utils.builder import PolicyBuilder
from ormai.utils.defaults import DEFAULT_DEV, DEFAULT_PROD


class TestPolicyBuilder:
    def test_basic_builder(self):
        policy = (
            PolicyBuilder(DEFAULT_PROD)
            .register_models(["Customer", "Order"])
            .build()
        )

        assert "Customer" in policy.models
        assert "Order" in policy.models
        assert policy.models["Customer"].allowed
        assert policy.models["Customer"].readable

    def test_tenant_scope(self):
        policy = (
            PolicyBuilder(DEFAULT_PROD)
            .register_models(["Customer"])
            .tenant_scope("tenant_id")
            .build()
        )

        row_policy = policy.models["Customer"].row_policy
        assert row_policy.tenant_scope_field == "tenant_id"

    def test_deny_patterns(self):
        policy = (
            PolicyBuilder(DEFAULT_PROD)
            .register_models(["Customer"])
            .deny_fields("*token*")
            .build()
        )

        assert "*token*" in policy.global_deny_patterns

    def test_dev_profile(self):
        policy = (
            PolicyBuilder(DEFAULT_DEV)
            .register_models(["Customer"])
            .build()
        )

        # Dev profile has higher limits
        assert policy.default_budget.max_rows == 1000

    def test_allow_relations(self):
        policy = (
            PolicyBuilder(DEFAULT_PROD)
            .register_models(["Customer", "Order"])
            .allow_relations({"Customer": ["orders"]})
            .build()
        )

        rel_policy = policy.models["Customer"].relations.get("orders")
        assert rel_policy is not None
        assert rel_policy.allowed


class TestPolicyBuilderWrites:
    """Tests for write extensions."""

    def test_enable_writes(self):
        """Test enabling writes on models."""
        policy = (
            PolicyBuilder(DEFAULT_PROD)
            .register_models(["Customer", "Order"])
            .enable_writes(["Order"])
            .build()
        )

        # Customer should not have writes enabled
        assert policy.models["Customer"].writable is False

        # Order should have writes enabled
        assert policy.models["Order"].writable is True
        write_policy = policy.models["Order"].write_policy
        assert write_policy is not None
        assert write_policy.enabled is True
        assert write_policy.allow_create is True
        assert write_policy.allow_update is True
        assert write_policy.allow_delete is True
        assert write_policy.allow_bulk is False

    def test_enable_writes_all_models(self):
        """Test enabling writes on all models."""
        policy = (
            PolicyBuilder(DEFAULT_PROD)
            .register_models(["Customer", "Order"])
            .enable_writes()  # No models specified = all
            .build()
        )

        assert policy.models["Customer"].writable is True
        assert policy.models["Order"].writable is True

    def test_enable_writes_selective_ops(self):
        """Test enabling only specific write operations."""
        policy = (
            PolicyBuilder(DEFAULT_PROD)
            .register_models(["Order"])
            .enable_writes(
                ["Order"],
                allow_create=True,
                allow_update=True,
                allow_delete=False,  # No deletes
            )
            .build()
        )

        write_policy = policy.models["Order"].write_policy
        assert write_policy.allow_create is True
        assert write_policy.allow_update is True
        assert write_policy.allow_delete is False

    def test_readonly_fields(self):
        """Test marking fields as readonly."""
        policy = (
            PolicyBuilder(DEFAULT_PROD)
            .register_models(["Order"])
            .enable_writes(["Order"])
            .readonly_fields("Order", ["id", "created_at", "tenant_id"])
            .build()
        )

        write_policy = policy.models["Order"].write_policy
        assert "id" in write_policy.readonly_fields
        assert "created_at" in write_policy.readonly_fields
        assert "tenant_id" in write_policy.readonly_fields

    def test_require_approval(self):
        """Test requiring approval for writes."""
        policy = (
            PolicyBuilder(DEFAULT_PROD)
            .register_models(["Order", "Customer"])
            .enable_writes()
            .require_approval(["Order"])  # Only Order requires approval
            .build()
        )

        assert policy.models["Order"].write_policy.require_approval is True
        assert policy.models["Customer"].write_policy.require_approval is False

    def test_allow_bulk_updates(self):
        """Test allowing bulk updates."""
        policy = (
            PolicyBuilder(DEFAULT_PROD)
            .register_models(["Order"])
            .enable_writes(["Order"])
            .allow_bulk_updates(["Order"], max_affected_rows=50)
            .build()
        )

        write_policy = policy.models["Order"].write_policy
        assert write_policy.allow_bulk is True
        assert write_policy.max_affected_rows == 50

    def test_soft_delete_default(self):
        """Test that soft delete is the default."""
        policy = (
            PolicyBuilder(DEFAULT_PROD)
            .register_models(["Order"])
            .enable_writes(["Order"])
            .build()
        )

        write_policy = policy.models["Order"].write_policy
        assert write_policy.soft_delete is True

    def test_hard_delete_option(self):
        """Test configuring hard delete."""
        policy = (
            PolicyBuilder(DEFAULT_PROD)
            .register_models(["Order"])
            .enable_writes(["Order"], soft_delete=False)
            .build()
        )

        write_policy = policy.models["Order"].write_policy
        assert write_policy.soft_delete is False

    def test_require_reason_from_profile(self):
        """Test that require_reason uses profile default."""
        # DEFAULT_PROD requires reason
        policy = (
            PolicyBuilder(DEFAULT_PROD)
            .register_models(["Order"])
            .enable_writes(["Order"])
            .build()
        )
        assert policy.models["Order"].write_policy.require_reason is True

        # DEFAULT_DEV does not require reason
        policy_dev = (
            PolicyBuilder(DEFAULT_DEV)
            .register_models(["Order"])
            .enable_writes(["Order"])
            .build()
        )
        assert policy_dev.models["Order"].write_policy.require_reason is False

    def test_chained_write_config(self):
        """Test chaining multiple write configuration methods."""
        policy = (
            PolicyBuilder(DEFAULT_PROD)
            .register_models(["Customer", "Order", "Product"])
            .enable_writes(["Order", "Product"], allow_delete=False)
            .readonly_fields("Order", ["id", "created_at"])
            .allow_bulk_updates(["Product"], max_affected_rows=100)
            .require_approval(["Order"])
            .build()
        )

        # Verify Order config
        order_wp = policy.models["Order"].write_policy
        assert order_wp.allow_delete is False
        assert order_wp.require_approval is True
        assert "id" in order_wp.readonly_fields

        # Verify Product config
        product_wp = policy.models["Product"].write_policy
        assert product_wp.allow_bulk is True
        assert product_wp.max_affected_rows == 100

        # Customer should not be writable
        assert policy.models["Customer"].writable is False
