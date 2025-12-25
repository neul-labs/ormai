"""
Policy Registry.

Central storage for versioned policies with support for:
- Publishing new policy versions
- Activating/deactivating versions
- Querying version history
- Computing diffs between versions
"""

import hashlib
import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from ormai.control_plane.models import PolicyDiff, PolicyVersion
from ormai.policy.models import Policy


def compute_policy_hash(policy: Policy) -> str:
    """Compute a stable hash of a policy for change detection."""
    # Serialize to JSON with sorted keys for stability
    policy_json = policy.model_dump_json(exclude_none=True)
    return hashlib.sha256(policy_json.encode()).hexdigest()[:16]


def compute_policy_diff(from_policy: Policy, to_policy: Policy) -> dict[str, Any]:
    """Compute differences between two policies."""
    changes: dict[str, Any] = {}

    from_models = set(from_policy.models.keys())
    to_models = set(to_policy.models.keys())

    # Added/removed models
    changes["added_models"] = list(to_models - from_models)
    changes["removed_models"] = list(from_models - to_models)

    # Modified models
    modified = {}
    for model in from_models & to_models:
        from_mp = from_policy.models[model]
        to_mp = to_policy.models[model]
        if from_mp != to_mp:
            model_changes = {}

            # Check field changes
            from_fields = set(from_mp.fields.keys())
            to_fields = set(to_mp.fields.keys())
            if from_fields != to_fields:
                model_changes["added_fields"] = list(to_fields - from_fields)
                model_changes["removed_fields"] = list(from_fields - to_fields)

            # Check relation changes
            from_rels = set(from_mp.relations.keys())
            to_rels = set(to_mp.relations.keys())
            if from_rels != to_rels:
                model_changes["added_relations"] = list(to_rels - from_rels)
                model_changes["removed_relations"] = list(from_rels - to_rels)

            # Check write policy
            if from_mp.write_policy != to_mp.write_policy:
                model_changes["write_policy_changed"] = True

            # Check budget
            if from_mp.budget != to_mp.budget:
                model_changes["budget_changed"] = True

            if model_changes:
                modified[model] = model_changes

    changes["modified_models"] = modified

    # Global changes
    global_changes = {}
    if from_policy.default_budget != to_policy.default_budget:
        global_changes["default_budget_changed"] = True
    if from_policy.writes_enabled != to_policy.writes_enabled:
        global_changes["writes_enabled"] = to_policy.writes_enabled
    if from_policy.require_tenant_scope != to_policy.require_tenant_scope:
        global_changes["require_tenant_scope"] = to_policy.require_tenant_scope

    changes["global_changes"] = global_changes

    return changes


class PolicyRegistry(ABC):
    """
    Abstract interface for policy registry.

    Implementations can store policies in:
    - In-memory (for testing)
    - SQL databases
    - Redis/key-value stores
    - Cloud services (S3, GCS, etc.)
    """

    @abstractmethod
    async def publish(
        self,
        policy: Policy,
        name: str,
        published_by: str,
        description: str | None = None,
        tags: list[str] | None = None,
        activate: bool = False,
    ) -> PolicyVersion:
        """
        Publish a new policy version.

        Args:
            policy: The policy to publish
            name: Human-readable name
            published_by: User who is publishing
            description: Optional description of changes
            tags: Optional tags for organization
            activate: Whether to immediately activate this version

        Returns:
            The created PolicyVersion
        """
        ...

    @abstractmethod
    async def activate(self, version: str) -> PolicyVersion:
        """
        Activate a policy version, making it the default.

        Only one version can be active at a time.
        """
        ...

    @abstractmethod
    async def deactivate(self, version: str) -> PolicyVersion:
        """
        Deactivate a policy version.
        """
        ...

    @abstractmethod
    async def get(self, version: str) -> PolicyVersion | None:
        """
        Get a specific policy version.
        """
        ...

    @abstractmethod
    async def get_active(self) -> PolicyVersion | None:
        """
        Get the currently active policy version.
        """
        ...

    @abstractmethod
    async def list_versions(
        self,
        name: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PolicyVersion]:
        """
        List policy versions with optional filters.
        """
        ...

    @abstractmethod
    async def delete(self, version: str) -> bool:
        """
        Delete a policy version.

        Returns True if deleted, False if not found.
        Active versions cannot be deleted.
        """
        ...

    async def diff(self, from_version: str, to_version: str) -> PolicyDiff | None:
        """
        Compute differences between two policy versions.
        """
        from_pv = await self.get(from_version)
        to_pv = await self.get(to_version)

        if not from_pv or not to_pv:
            return None

        changes = compute_policy_diff(from_pv.policy, to_pv.policy)

        # Build summary
        summary_parts = []
        if changes.get("added_models"):
            summary_parts.append(f"Added models: {', '.join(changes['added_models'])}")
        if changes.get("removed_models"):
            summary_parts.append(f"Removed models: {', '.join(changes['removed_models'])}")
        if changes.get("modified_models"):
            summary_parts.append(f"Modified {len(changes['modified_models'])} models")
        if changes.get("global_changes"):
            summary_parts.append("Global policy changes")

        return PolicyDiff(
            from_version=from_version,
            to_version=to_version,
            added_models=changes.get("added_models", []),
            removed_models=changes.get("removed_models", []),
            modified_models=changes.get("modified_models", {}),
            global_changes=changes.get("global_changes", {}),
            summary="; ".join(summary_parts) if summary_parts else "No changes",
        )


class InMemoryPolicyRegistry(PolicyRegistry):
    """
    In-memory policy registry for testing and development.
    """

    def __init__(self) -> None:
        self._versions: dict[str, PolicyVersion] = {}
        self._active_version: str | None = None
        self._version_counter = 0

    async def publish(
        self,
        policy: Policy,
        name: str,
        published_by: str,
        description: str | None = None,
        tags: list[str] | None = None,
        activate: bool = False,
    ) -> PolicyVersion:
        self._version_counter += 1
        version_id = f"v{self._version_counter}"

        pv = PolicyVersion(
            version=version_id,
            name=name,
            policy=policy,
            published_at=datetime.utcnow(),
            published_by=published_by,
            description=description,
            tags=tags or [],
            is_active=False,
            policy_hash=compute_policy_hash(policy),
        )

        self._versions[version_id] = pv

        if activate:
            await self.activate(version_id)
            pv = self._versions[version_id]

        return pv

    async def activate(self, version: str) -> PolicyVersion:
        if version not in self._versions:
            raise ValueError(f"Version {version} not found")

        # Deactivate current active
        if self._active_version and self._active_version in self._versions:
            old_pv = self._versions[self._active_version]
            self._versions[self._active_version] = PolicyVersion(
                **{**old_pv.model_dump(), "is_active": False}
            )

        # Activate new version
        pv = self._versions[version]
        new_pv = PolicyVersion(**{**pv.model_dump(), "is_active": True})
        self._versions[version] = new_pv
        self._active_version = version

        return new_pv

    async def deactivate(self, version: str) -> PolicyVersion:
        if version not in self._versions:
            raise ValueError(f"Version {version} not found")

        pv = self._versions[version]
        new_pv = PolicyVersion(**{**pv.model_dump(), "is_active": False})
        self._versions[version] = new_pv

        if self._active_version == version:
            self._active_version = None

        return new_pv

    async def get(self, version: str) -> PolicyVersion | None:
        return self._versions.get(version)

    async def get_active(self) -> PolicyVersion | None:
        if self._active_version:
            return self._versions.get(self._active_version)
        return None

    async def list_versions(
        self,
        name: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PolicyVersion]:
        versions = list(self._versions.values())

        # Filter by name
        if name:
            versions = [v for v in versions if v.name == name]

        # Filter by tags
        if tags:
            versions = [v for v in versions if any(t in v.tags for t in tags)]

        # Sort by published_at descending
        versions.sort(key=lambda v: v.published_at, reverse=True)

        # Pagination
        return versions[offset : offset + limit]

    async def delete(self, version: str) -> bool:
        if version not in self._versions:
            return False

        pv = self._versions[version]
        if pv.is_active:
            raise ValueError("Cannot delete active version")

        del self._versions[version]
        return True


class JsonFilePolicyRegistry(PolicyRegistry):
    """
    File-based policy registry using JSON files.

    Stores each version as a separate JSON file for easy versioning with git.
    """

    def __init__(self, directory: str) -> None:
        import os

        self.directory = directory
        os.makedirs(directory, exist_ok=True)
        self._metadata_file = os.path.join(directory, "_metadata.json")
        self._load_metadata()

    def _load_metadata(self) -> None:
        import os

        if os.path.exists(self._metadata_file):
            with open(self._metadata_file) as f:
                data = json.load(f)
                self._active_version = data.get("active_version")
                self._version_counter = data.get("version_counter", 0)
        else:
            self._active_version = None
            self._version_counter = 0

    def _save_metadata(self) -> None:
        with open(self._metadata_file, "w") as f:
            json.dump(
                {
                    "active_version": self._active_version,
                    "version_counter": self._version_counter,
                },
                f,
                indent=2,
            )

    def _version_file(self, version: str) -> str:
        import os

        return os.path.join(self.directory, f"{version}.json")

    async def publish(
        self,
        policy: Policy,
        name: str,
        published_by: str,
        description: str | None = None,
        tags: list[str] | None = None,
        activate: bool = False,
    ) -> PolicyVersion:
        self._version_counter += 1
        version_id = f"v{self._version_counter}"

        pv = PolicyVersion(
            version=version_id,
            name=name,
            policy=policy,
            published_at=datetime.utcnow(),
            published_by=published_by,
            description=description,
            tags=tags or [],
            is_active=activate,
            policy_hash=compute_policy_hash(policy),
        )

        # Save version file
        with open(self._version_file(version_id), "w") as f:
            f.write(pv.model_dump_json(indent=2))

        if activate:
            self._active_version = version_id

        self._save_metadata()
        return pv

    async def activate(self, version: str) -> PolicyVersion:
        import os

        version_file = self._version_file(version)
        if not os.path.exists(version_file):
            raise ValueError(f"Version {version} not found")

        # Deactivate old version
        if self._active_version:
            old_file = self._version_file(self._active_version)
            if os.path.exists(old_file):
                with open(old_file) as f:
                    old_pv = PolicyVersion.model_validate_json(f.read())
                old_pv = PolicyVersion(**{**old_pv.model_dump(), "is_active": False})
                with open(old_file, "w") as f:
                    f.write(old_pv.model_dump_json(indent=2))

        # Activate new version
        with open(version_file) as f:
            pv = PolicyVersion.model_validate_json(f.read())

        new_pv = PolicyVersion(**{**pv.model_dump(), "is_active": True})
        with open(version_file, "w") as f:
            f.write(new_pv.model_dump_json(indent=2))

        self._active_version = version
        self._save_metadata()
        return new_pv

    async def deactivate(self, version: str) -> PolicyVersion:
        import os

        version_file = self._version_file(version)
        if not os.path.exists(version_file):
            raise ValueError(f"Version {version} not found")

        with open(version_file) as f:
            pv = PolicyVersion.model_validate_json(f.read())

        new_pv = PolicyVersion(**{**pv.model_dump(), "is_active": False})
        with open(version_file, "w") as f:
            f.write(new_pv.model_dump_json(indent=2))

        if self._active_version == version:
            self._active_version = None
            self._save_metadata()

        return new_pv

    async def get(self, version: str) -> PolicyVersion | None:
        import os

        version_file = self._version_file(version)
        if not os.path.exists(version_file):
            return None

        with open(version_file) as f:
            return PolicyVersion.model_validate_json(f.read())

    async def get_active(self) -> PolicyVersion | None:
        if self._active_version:
            return await self.get(self._active_version)
        return None

    async def list_versions(
        self,
        name: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PolicyVersion]:
        import os

        versions = []
        for filename in os.listdir(self.directory):
            if filename.endswith(".json") and not filename.startswith("_"):
                filepath = os.path.join(self.directory, filename)
                with open(filepath) as f:
                    pv = PolicyVersion.model_validate_json(f.read())
                    versions.append(pv)

        # Filter by name
        if name:
            versions = [v for v in versions if v.name == name]

        # Filter by tags
        if tags:
            versions = [v for v in versions if any(t in v.tags for t in tags)]

        # Sort by published_at descending
        versions.sort(key=lambda v: v.published_at, reverse=True)

        return versions[offset : offset + limit]

    async def delete(self, version: str) -> bool:
        import os

        version_file = self._version_file(version)
        if not os.path.exists(version_file):
            return False

        with open(version_file) as f:
            pv = PolicyVersion.model_validate_json(f.read())

        if pv.is_active:
            raise ValueError("Cannot delete active version")

        os.remove(version_file)
        return True
