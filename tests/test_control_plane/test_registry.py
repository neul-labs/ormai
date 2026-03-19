"""Tests for Policy Registry."""

import pytest
from datetime import datetime

from ormai.control_plane.registry import (
    InMemoryPolicyRegistry,
    JsonFilePolicyRegistry,
    compute_policy_hash,
    compute_policy_diff,
)
from ormai.policy.models import (
    Policy,
    ModelPolicy,
    FieldPolicy,
    FieldAction,
    Budget,
)


@pytest.fixture
def sample_policy() -> Policy:
    """Create a sample policy for testing."""
    return Policy(
        models={
            "Customer": ModelPolicy(
                allowed=True,
                readable=True,
                fields={
                    "id": FieldPolicy(action=FieldAction.ALLOW),
                    "name": FieldPolicy(action=FieldAction.ALLOW),
                    "email": FieldPolicy(action=FieldAction.MASK),
                },
            ),
            "Order": ModelPolicy(
                allowed=True,
                readable=True,
            ),
        },
        default_budget=Budget(max_rows=100),
    )


@pytest.fixture
def modified_policy() -> Policy:
    """Create a modified policy for diff testing."""
    return Policy(
        models={
            "Customer": ModelPolicy(
                allowed=True,
                readable=True,
                fields={
                    "id": FieldPolicy(action=FieldAction.ALLOW),
                    "name": FieldPolicy(action=FieldAction.ALLOW),
                    "email": FieldPolicy(action=FieldAction.MASK),
                    "phone": FieldPolicy(action=FieldAction.MASK),  # Added
                },
            ),
            # Order removed
            "Product": ModelPolicy(  # Added
                allowed=True,
                readable=True,
            ),
        },
        default_budget=Budget(max_rows=200),  # Changed
    )


class TestPolicyHash:
    """Tests for policy hashing."""

    def test_hash_is_stable(self, sample_policy: Policy) -> None:
        """Same policy produces same hash."""
        hash1 = compute_policy_hash(sample_policy)
        hash2 = compute_policy_hash(sample_policy)
        assert hash1 == hash2

    def test_hash_detects_changes(
        self, sample_policy: Policy, modified_policy: Policy
    ) -> None:
        """Different policies produce different hashes."""
        hash1 = compute_policy_hash(sample_policy)
        hash2 = compute_policy_hash(modified_policy)
        assert hash1 != hash2


class TestPolicyDiff:
    """Tests for policy diffing."""

    def test_diff_detects_added_models(
        self, sample_policy: Policy, modified_policy: Policy
    ) -> None:
        """Diff shows added models."""
        diff = compute_policy_diff(sample_policy, modified_policy)
        assert "Product" in diff["added_models"]

    def test_diff_detects_removed_models(
        self, sample_policy: Policy, modified_policy: Policy
    ) -> None:
        """Diff shows removed models."""
        diff = compute_policy_diff(sample_policy, modified_policy)
        assert "Order" in diff["removed_models"]

    def test_diff_detects_modified_models(
        self, sample_policy: Policy, modified_policy: Policy
    ) -> None:
        """Diff shows modified models."""
        diff = compute_policy_diff(sample_policy, modified_policy)
        assert "Customer" in diff["modified_models"]
        assert "phone" in diff["modified_models"]["Customer"].get("added_fields", [])

    def test_diff_detects_global_changes(
        self, sample_policy: Policy, modified_policy: Policy
    ) -> None:
        """Diff shows global changes."""
        diff = compute_policy_diff(sample_policy, modified_policy)
        assert diff["global_changes"].get("default_budget_changed") is True


class TestInMemoryPolicyRegistry:
    """Tests for in-memory policy registry."""

    @pytest.fixture
    def registry(self) -> InMemoryPolicyRegistry:
        """Create a registry for testing."""
        return InMemoryPolicyRegistry()

    @pytest.mark.asyncio
    async def test_publish_creates_version(
        self, registry: InMemoryPolicyRegistry, sample_policy: Policy
    ) -> None:
        """Publishing creates a new version."""
        pv = await registry.publish(
            policy=sample_policy,
            name="test-policy",
            published_by="test-user",
            description="Initial version",
        )
        assert pv.version == "v1"
        assert pv.name == "test-policy"
        assert pv.published_by == "test-user"
        assert pv.is_active is False

    @pytest.mark.asyncio
    async def test_publish_with_activate(
        self, registry: InMemoryPolicyRegistry, sample_policy: Policy
    ) -> None:
        """Publishing with activate=True makes it active."""
        pv = await registry.publish(
            policy=sample_policy,
            name="test-policy",
            published_by="test-user",
            activate=True,
        )
        assert pv.is_active is True

        active = await registry.get_active()
        assert active is not None
        assert active.version == pv.version

    @pytest.mark.asyncio
    async def test_activate_deactivates_previous(
        self, registry: InMemoryPolicyRegistry, sample_policy: Policy
    ) -> None:
        """Activating a version deactivates the previous one."""
        pv1 = await registry.publish(
            policy=sample_policy,
            name="test-policy",
            published_by="test-user",
            activate=True,
        )
        pv2 = await registry.publish(
            policy=sample_policy,
            name="test-policy",
            published_by="test-user",
        )

        await registry.activate(pv2.version)

        old = await registry.get(pv1.version)
        new = await registry.get(pv2.version)

        assert old is not None
        assert old.is_active is False
        assert new is not None
        assert new.is_active is True

    @pytest.mark.asyncio
    async def test_deactivate(
        self, registry: InMemoryPolicyRegistry, sample_policy: Policy
    ) -> None:
        """Deactivating a version works."""
        pv = await registry.publish(
            policy=sample_policy,
            name="test-policy",
            published_by="test-user",
            activate=True,
        )

        await registry.deactivate(pv.version)

        updated = await registry.get(pv.version)
        assert updated is not None
        assert updated.is_active is False

        active = await registry.get_active()
        assert active is None

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(
        self, registry: InMemoryPolicyRegistry
    ) -> None:
        """Getting nonexistent version returns None."""
        result = await registry.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_versions(
        self, registry: InMemoryPolicyRegistry, sample_policy: Policy
    ) -> None:
        """List versions returns all versions."""
        for i in range(5):
            await registry.publish(
                policy=sample_policy,
                name=f"policy-{i % 2}",
                published_by="test-user",
                tags=["tag-a"] if i % 2 == 0 else ["tag-b"],
            )

        # List all
        all_versions = await registry.list_versions()
        assert len(all_versions) == 5

        # Filter by name
        named = await registry.list_versions(name="policy-0")
        assert len(named) == 3

        # Filter by tags
        tagged = await registry.list_versions(tags=["tag-a"])
        assert len(tagged) == 3

        # Pagination
        paginated = await registry.list_versions(limit=2, offset=1)
        assert len(paginated) == 2

    @pytest.mark.asyncio
    async def test_delete_version(
        self, registry: InMemoryPolicyRegistry, sample_policy: Policy
    ) -> None:
        """Deleting a version removes it."""
        pv = await registry.publish(
            policy=sample_policy,
            name="test-policy",
            published_by="test-user",
        )

        result = await registry.delete(pv.version)
        assert result is True

        deleted = await registry.get(pv.version)
        assert deleted is None

    @pytest.mark.asyncio
    async def test_delete_active_fails(
        self, registry: InMemoryPolicyRegistry, sample_policy: Policy
    ) -> None:
        """Cannot delete active version."""
        pv = await registry.publish(
            policy=sample_policy,
            name="test-policy",
            published_by="test-user",
            activate=True,
        )

        with pytest.raises(ValueError, match="Cannot delete active"):
            await registry.delete(pv.version)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(
        self, registry: InMemoryPolicyRegistry
    ) -> None:
        """Deleting nonexistent version returns False."""
        result = await registry.delete("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_diff_versions(
        self,
        registry: InMemoryPolicyRegistry,
        sample_policy: Policy,
        modified_policy: Policy,
    ) -> None:
        """Diff between versions works."""
        pv1 = await registry.publish(
            policy=sample_policy,
            name="test-policy",
            published_by="test-user",
        )
        pv2 = await registry.publish(
            policy=modified_policy,
            name="test-policy",
            published_by="test-user",
        )

        diff = await registry.diff(pv1.version, pv2.version)
        assert diff is not None
        assert "Product" in diff.added_models
        assert "Order" in diff.removed_models
        assert "Customer" in diff.modified_models


class TestJsonFilePolicyRegistry:
    """Tests for file-based policy registry."""

    @pytest.fixture
    def registry(self, tmp_path) -> JsonFilePolicyRegistry:
        """Create a registry for testing."""
        return JsonFilePolicyRegistry(str(tmp_path / "policies"))

    @pytest.mark.asyncio
    async def test_publish_and_get(
        self, registry: JsonFilePolicyRegistry, sample_policy: Policy
    ) -> None:
        """Publishing and getting works."""
        pv = await registry.publish(
            policy=sample_policy,
            name="test-policy",
            published_by="test-user",
        )

        retrieved = await registry.get(pv.version)
        assert retrieved is not None
        assert retrieved.name == pv.name
        assert retrieved.policy == sample_policy

    @pytest.mark.asyncio
    async def test_activate_persists(
        self, registry: JsonFilePolicyRegistry, sample_policy: Policy
    ) -> None:
        """Activation state is persisted."""
        pv = await registry.publish(
            policy=sample_policy,
            name="test-policy",
            published_by="test-user",
        )

        await registry.activate(pv.version)

        # Create a new registry instance to verify persistence
        registry2 = JsonFilePolicyRegistry(registry.directory)
        active = await registry2.get_active()
        assert active is not None
        assert active.version == pv.version

    @pytest.mark.asyncio
    async def test_list_versions(
        self, registry: JsonFilePolicyRegistry, sample_policy: Policy
    ) -> None:
        """List versions works with files."""
        for i in range(3):
            await registry.publish(
                policy=sample_policy,
                name=f"policy-{i}",
                published_by="test-user",
            )

        versions = await registry.list_versions()
        assert len(versions) == 3

    @pytest.mark.asyncio
    async def test_delete_removes_file(
        self, registry: JsonFilePolicyRegistry, sample_policy: Policy
    ) -> None:
        """Deleting removes the file."""
        import os

        pv = await registry.publish(
            policy=sample_policy,
            name="test-policy",
            published_by="test-user",
        )

        version_file = registry._version_file(pv.version)
        assert os.path.exists(version_file)

        await registry.delete(pv.version)
        assert not os.path.exists(version_file)
