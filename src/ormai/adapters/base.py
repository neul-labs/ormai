"""
Abstract base adapter interface.

All ORM adapters must implement this interface to be compatible with OrmAI.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from ormai.core.context import RunContext
from ormai.core.dsl import (
    AggregateRequest,
    AggregateResult,
    BulkUpdateRequest,
    BulkUpdateResult,
    CreateRequest,
    CreateResult,
    DeleteRequest,
    DeleteResult,
    FilterClause,
    GetRequest,
    GetResult,
    QueryRequest,
    QueryResult,
    UpdateRequest,
    UpdateResult,
)
from ormai.core.types import SchemaMetadata
from ormai.policy.models import Policy

T = TypeVar("T")


@dataclass
class CompiledQuery:
    """
    Result of query compilation.

    Contains the ORM-specific query object and metadata needed for execution.
    """

    # The compiled query object (type depends on adapter)
    query: Any

    # Original request for reference
    request: QueryRequest | GetRequest | AggregateRequest

    # Fields to select (after policy filtering)
    select_fields: list[str] = field(default_factory=list)

    # Filters injected by policy (for auditing)
    injected_filters: list[FilterClause] = field(default_factory=list)

    # Policy decisions made during compilation
    policy_decisions: list[str] = field(default_factory=list)

    # Statement timeout in milliseconds
    timeout_ms: int | None = None


class OrmAdapter(ABC):
    """
    Abstract base class for ORM adapters.

    Adapters are responsible for:
    1. Schema introspection
    2. Query compilation (DSL -> ORM query)
    3. Query execution
    4. Session/transaction management
    """

    @abstractmethod
    async def introspect(self) -> SchemaMetadata:
        """
        Introspect the database schema.

        Returns metadata about all models, fields, relations, and types.
        This is called once at startup and cached.
        """
        ...

    @abstractmethod
    def compile_query(
        self,
        request: QueryRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """
        Compile a query request into an ORM-specific query.

        This method:
        1. Validates the request against policies
        2. Injects scope filters
        3. Builds the ORM query
        4. Returns a CompiledQuery with the result

        Raises policy errors if validation fails.
        """
        ...

    @abstractmethod
    def compile_get(
        self,
        request: GetRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """
        Compile a get-by-id request into an ORM-specific query.
        """
        ...

    @abstractmethod
    def compile_aggregate(
        self,
        request: AggregateRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """
        Compile an aggregation request into an ORM-specific query.
        """
        ...

    @abstractmethod
    async def execute_query(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> QueryResult:
        """
        Execute a compiled query and return results.

        Results are returned as dicts with field redaction already applied.
        """
        ...

    @abstractmethod
    async def execute_get(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> GetResult:
        """
        Execute a compiled get request and return the result.
        """
        ...

    @abstractmethod
    async def execute_aggregate(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> AggregateResult:
        """
        Execute a compiled aggregation and return the result.
        """
        ...

    @abstractmethod
    async def transaction(
        self,
        ctx: RunContext,
        fn: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Execute a function within a transaction.

        The transaction is committed if the function completes successfully,
        or rolled back if an exception is raised.
        """
        ...

    # =========================================================================
    # MUTATION METHODS (Phase 2)
    # =========================================================================

    def compile_create(
        self,
        request: CreateRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """
        Compile a create request.

        Validates write permissions and prepares the insert statement.
        """
        raise NotImplementedError("Create not implemented for this adapter")

    def compile_update(
        self,
        request: UpdateRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """
        Compile an update request.

        Validates write permissions and prepares the update statement.
        """
        raise NotImplementedError("Update not implemented for this adapter")

    def compile_delete(
        self,
        request: DeleteRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """
        Compile a delete request.

        Validates delete permissions and prepares the delete statement.
        """
        raise NotImplementedError("Delete not implemented for this adapter")

    def compile_bulk_update(
        self,
        request: BulkUpdateRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """
        Compile a bulk update request.

        Validates bulk operation permissions and prepares the update statements.
        """
        raise NotImplementedError("Bulk update not implemented for this adapter")

    async def execute_create(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> CreateResult:
        """
        Execute a compiled create request.
        """
        raise NotImplementedError("Create not implemented for this adapter")

    async def execute_update(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> UpdateResult:
        """
        Execute a compiled update request.
        """
        raise NotImplementedError("Update not implemented for this adapter")

    async def execute_delete(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> DeleteResult:
        """
        Execute a compiled delete request.
        """
        raise NotImplementedError("Delete not implemented for this adapter")

    async def execute_bulk_update(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> BulkUpdateResult:
        """
        Execute a compiled bulk update request.
        """
        raise NotImplementedError("Bulk update not implemented for this adapter")

    def sync_introspect(self) -> SchemaMetadata:
        """
        Synchronous version of introspect.

        Default implementation runs the async version in an event loop.
        Adapters may override for better sync support.
        """
        import asyncio
        return asyncio.get_event_loop().run_until_complete(self.introspect())
