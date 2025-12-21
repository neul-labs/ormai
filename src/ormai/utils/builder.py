"""
Policy builder for fluent policy construction.
"""

import fnmatch

from ormai.core.types import SchemaMetadata
from ormai.policy.models import (
    FieldAction,
    FieldPolicy,
    ModelPolicy,
    Policy,
    RelationPolicy,
    RowPolicy,
    WritePolicy,
)
from ormai.utils.defaults import DEFAULT_PROD, DefaultsProfile


class PolicyBuilder:
    """
    Fluent builder for constructing policies.

    Example:
        policy = (
            PolicyBuilder(DEFAULT_PROD)
            .register_models([Customer, Order])
            .deny_fields("*password*", "*secret*")
            .mask_fields(["email", "phone"])
            .allow_relations({"Order": ["customer"]})
            .tenant_scope("tenant_id")
            .build()
        )
    """

    # Default patterns for sensitive fields
    DEFAULT_DENY_PATTERNS = [
        "*password*",
        "*secret*",
        "*token*",
        "*api_key*",
        "*apikey*",
        "*private_key*",
        "*privatekey*",
    ]

    DEFAULT_MASK_PATTERNS = [
        "email",
        "phone",
        "phone_number",
        "address",
        "ip",
        "ip_address",
        "ssn",
        "dob",
        "date_of_birth",
    ]

    def __init__(
        self,
        profile: DefaultsProfile = DEFAULT_PROD,
        schema: SchemaMetadata | None = None,
    ) -> None:
        """
        Initialize the builder.

        Args:
            profile: Default profile to use
            schema: Optional schema for auto-discovery
        """
        self.profile = profile
        self.schema = schema

        # State
        self._models: dict[str, ModelPolicy] = {}
        self._global_deny_patterns: list[str] = list(self.DEFAULT_DENY_PATTERNS)
        self._global_mask_patterns: list[str] = list(self.DEFAULT_MASK_PATTERNS)
        self._tenant_field: str | None = None
        self._ownership_field: str | None = None

    def register_models(
        self,
        models: list[type] | list[str],
        readable: bool = True,
        writable: bool | None = None,
    ) -> "PolicyBuilder":
        """
        Register models to be accessible.

        Args:
            models: List of model classes or model names
            readable: Whether models are readable
            writable: Whether models are writable (defaults to profile setting)
        """
        if writable is None:
            writable = self.profile.writes_enabled

        for model in models:
            name = model.__name__ if isinstance(model, type) else model
            self._models[name] = ModelPolicy(
                allowed=True,
                readable=readable,
                writable=writable,
                budget=self.profile.to_budget(),
            )

        return self

    def deny_fields(self, *patterns: str) -> "PolicyBuilder":
        """
        Add field patterns to deny (hide completely).

        Uses glob-style patterns (e.g., "*password*").
        """
        self._global_deny_patterns.extend(patterns)
        return self

    def mask_fields(self, fields: list[str]) -> "PolicyBuilder":
        """
        Add field names to mask (partial redaction).
        """
        self._global_mask_patterns.extend(fields)
        return self

    def allow_relations(
        self,
        relations: dict[str, list[str]],
        max_depth: int = 1,
    ) -> "PolicyBuilder":
        """
        Configure allowed relations per model.

        Args:
            relations: Dict of {model_name: [relation_names]}
            max_depth: Maximum include depth
        """
        for model_name, rel_names in relations.items():
            if model_name not in self._models:
                continue

            model_policy = self._models[model_name]
            new_relations = dict(model_policy.relations)

            for rel_name in rel_names:
                new_relations[rel_name] = RelationPolicy(
                    allowed=True,
                    max_depth=max_depth,
                )

            # Create new ModelPolicy with updated relations
            self._models[model_name] = ModelPolicy(
                allowed=model_policy.allowed,
                readable=model_policy.readable,
                writable=model_policy.writable,
                fields=model_policy.fields,
                relations=new_relations,
                row_policy=model_policy.row_policy,
                write_policy=model_policy.write_policy,
                budget=model_policy.budget,
            )

        return self

    def tenant_scope(self, field: str) -> "PolicyBuilder":
        """
        Set the tenant scope field.

        This field will be used to automatically filter all queries
        by the current tenant.
        """
        self._tenant_field = field
        return self

    def ownership_scope(self, field: str) -> "PolicyBuilder":
        """
        Set the ownership scope field.

        This field can be used to filter queries by owner.
        """
        self._ownership_field = field
        return self

    def for_role(self, role: str) -> "RoleOverlayBuilder":
        """
        Start building role-specific overrides.

        Returns a RoleOverlayBuilder for fluent configuration.
        """
        return RoleOverlayBuilder(self, role)

    def build(self) -> Policy:
        """
        Build the final policy.

        Applies field patterns and row policies to all registered models.
        """
        # Apply field patterns to all models
        for model_name, model_policy in self._models.items():
            updated_fields = dict(model_policy.fields)

            # Get fields from schema if available
            if self.schema:
                model_meta = self.schema.get_model(model_name)
                if model_meta:
                    for field_name in model_meta.fields:
                        action = self._get_field_action(field_name)
                        if action != FieldAction.ALLOW:
                            updated_fields[field_name] = FieldPolicy(action=action)

            # Apply row policy
            row_policy = RowPolicy(
                tenant_scope_field=self._tenant_field,
                ownership_scope_field=self._ownership_field,
                require_scope=self.profile.require_tenant_scope,
            )

            # Update model policy
            self._models[model_name] = ModelPolicy(
                allowed=model_policy.allowed,
                readable=model_policy.readable,
                writable=model_policy.writable,
                fields=updated_fields,
                relations=model_policy.relations,
                row_policy=row_policy,
                write_policy=model_policy.write_policy,
                budget=model_policy.budget,
            )

        return Policy(
            models=self._models,
            default_budget=self.profile.to_budget(),
            default_row_policy=RowPolicy(
                tenant_scope_field=self._tenant_field,
                require_scope=self.profile.require_tenant_scope,
            ),
            global_deny_patterns=self._global_deny_patterns,
            global_mask_patterns=self._global_mask_patterns,
            require_tenant_scope=self.profile.require_tenant_scope,
            writes_enabled=self.profile.writes_enabled,
        )

    def _get_field_action(self, field_name: str) -> FieldAction:
        """Determine the action for a field based on patterns."""
        field_lower = field_name.lower()

        # Check deny patterns
        for pattern in self._global_deny_patterns:
            if fnmatch.fnmatch(field_lower, pattern.lower()):
                return FieldAction.DENY

        # Check mask patterns
        for pattern in self._global_mask_patterns:
            if field_lower == pattern.lower():
                return FieldAction.MASK

        return FieldAction.ALLOW


class RoleOverlayBuilder:
    """
    Builder for role-specific policy overrides.
    """

    def __init__(self, parent: PolicyBuilder, role: str) -> None:
        self.parent = parent
        self.role = role

    def allow_writes(self, models: list[str]) -> "RoleOverlayBuilder":
        """Allow write access to specific models for this role."""
        # This would be implemented with role-based overlays
        # For now, just modify the parent
        for model_name in models:
            if model_name in self.parent._models:
                model = self.parent._models[model_name]
                self.parent._models[model_name] = ModelPolicy(
                    allowed=model.allowed,
                    readable=model.readable,
                    writable=True,
                    fields=model.fields,
                    relations=model.relations,
                    row_policy=model.row_policy,
                    write_policy=WritePolicy(enabled=True, allow_update=True),
                    budget=model.budget,
                )
        return self

    def end(self) -> PolicyBuilder:
        """Return to the parent builder."""
        return self.parent
