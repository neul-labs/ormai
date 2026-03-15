"""
Toolset factory for building tool registries from policy.
"""

from ormai.adapters.base import OrmAdapter
from ormai.core.types import SchemaMetadata
from ormai.policy.models import Policy
from ormai.tools.generic import (
    AggregateTool,
    DescribeSchemaTool,
    GetTool,
    QueryTool,
)
from ormai.tools.registry import ToolRegistry


class ToolsetFactory:
    """
    Factory for creating tool registries from policy configuration.

    Creates the appropriate set of tools based on policy settings.
    """

    def __init__(
        self,
        adapter: OrmAdapter,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> None:
        """
        Initialize the factory.

        Args:
            adapter: The ORM adapter to use
            policy: Policy configuration
            schema: Schema metadata
        """
        self.adapter = adapter
        self.policy = policy
        self.schema = schema

    def create(self) -> ToolRegistry:
        """
        Create a tool registry with all enabled tools.

        Returns a ToolRegistry containing:
        - db.describe_schema (always)
        - db.query (if reads enabled)
        - db.get (if reads enabled)
        - db.aggregate (if reads enabled)
        - write tools (if writes enabled in policy)
        """
        registry = ToolRegistry()

        # Always register describe_schema
        registry.register(
            DescribeSchemaTool(schema=self.schema, policy=self.policy)
        )

        # Register read tools
        registry.register(
            QueryTool(adapter=self.adapter, policy=self.policy, schema=self.schema)
        )
        registry.register(
            GetTool(adapter=self.adapter, policy=self.policy, schema=self.schema)
        )
        registry.register(
            AggregateTool(adapter=self.adapter, policy=self.policy, schema=self.schema)
        )

        # Write tools would be added here if enabled
        # if self.policy.writes_enabled:
        #     registry.register(CreateTool(...))
        #     registry.register(UpdateTool(...))
        #     registry.register(DeleteTool(...))

        return registry

    @classmethod
    def from_policy(
        cls,
        policy: Policy,
        adapter: OrmAdapter,
        schema: SchemaMetadata | None = None,
    ) -> ToolRegistry:
        """
        Convenience method to create a toolset from policy.

        If schema is not provided, it will be introspected from the adapter.
        """
        if schema is None:
            schema = adapter.sync_introspect()

        factory = cls(adapter=adapter, policy=policy, schema=schema)
        return factory.create()
