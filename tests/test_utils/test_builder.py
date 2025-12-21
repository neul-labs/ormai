"""
Tests for the policy builder.
"""

from ormai.policy.models import FieldAction
from ormai.utils.builder import PolicyBuilder
from ormai.utils.defaults import DEFAULT_PROD, DEFAULT_DEV


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
