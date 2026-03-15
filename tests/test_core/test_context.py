"""
Tests for the context module.
"""

from ormai.core.context import Principal, RunContext


class TestPrincipal:
    def test_basic_principal(self):
        p = Principal(
            tenant_id="tenant-1",
            user_id="user-1",
        )
        assert p.tenant_id == "tenant-1"
        assert p.user_id == "user-1"
        assert p.roles == ()

    def test_principal_with_roles(self):
        p = Principal(
            tenant_id="tenant-1",
            user_id="user-1",
            roles=("admin", "support"),
        )
        assert p.has_role("admin")
        assert p.has_role("support")
        assert not p.has_role("guest")

    def test_has_any_role(self):
        p = Principal(
            tenant_id="tenant-1",
            user_id="user-1",
            roles=("user",),
        )
        assert p.has_any_role("admin", "user")
        assert not p.has_any_role("admin", "support")


class TestRunContext:
    def test_create_context(self):
        ctx = RunContext.create(
            tenant_id="tenant-1",
            user_id="user-1",
            db=None,
        )
        assert ctx.principal.tenant_id == "tenant-1"
        assert ctx.principal.user_id == "user-1"
        assert ctx.request_id is not None  # Auto-generated

    def test_context_with_trace(self):
        ctx = RunContext.create(
            tenant_id="tenant-1",
            user_id="user-1",
            db=None,
            trace_id="trace-123",
        )
        assert ctx.trace_id == "trace-123"

    def test_context_with_roles(self):
        ctx = RunContext.create(
            tenant_id="tenant-1",
            user_id="user-1",
            db=None,
            roles=["admin", "support"],
        )
        assert ctx.principal.has_role("admin")
