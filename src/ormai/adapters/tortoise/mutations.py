"""
Mutation execution methods for Tortoise ORM adapter.

This module contains the mutation compilation and execution logic
(create, update, delete, bulk_update).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from ormai.adapters.base import CompiledQuery
from ormai.core.context import RunContext
from ormai.core.dsl import (
    BulkUpdateRequest,
    BulkUpdateResult,
    CreateRequest,
    CreateResult,
    DeleteRequest,
    DeleteResult,
    UpdateRequest,
    UpdateResult,
)
from ormai.core.types import SchemaMetadata
from ormai.policy.models import Policy

if TYPE_CHECKING:
    from ormai.adapters.tortoise.adapter import TortoiseAdapter


class MutationExecutor:
    """
    Handles mutation compilation and execution for Tortoise ORM adapter.

    Contains methods for compiling and executing create, update,
    delete, and bulk_update operations.
    """

    def __init__(self, adapter: TortoiseAdapter) -> None:
        """Initialize with reference to parent adapter."""
        self._adapter = adapter

    # =========================================================================
    # COMPILATION METHODS
    # =========================================================================

    def compile_create(
        self,
        request: CreateRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,  # noqa: ARG002
    ) -> CompiledQuery:
        """Compile a create request."""
        decision = self._adapter.compiler.policy_engine.validate_create(
            request, ctx
        )

        model_class = self._adapter.compiler.model_map.get(request.model)
        if model_class is None:
            raise ValueError(f"Model not found: {request.model}")

        # Prepare data with injected scope values
        data = dict(request.data)
        row_policy = policy.get_row_policy(request.model)
        if row_policy.tenant_scope_field and ctx.principal.tenant_id:
            data[row_policy.tenant_scope_field] = ctx.principal.tenant_id

        return CompiledQuery(
            query={"model_class": model_class, "data": data},
            request=request,
            select_fields=decision.allowed_fields,
            injected_filters=decision.injected_filters,
            policy_decisions=decision.decisions,
        )

    def compile_update(
        self,
        request: UpdateRequest,
        ctx: RunContext,
        policy: Policy,  # noqa: ARG002
        schema: SchemaMetadata,  # noqa: ARG002
    ) -> CompiledQuery:
        """Compile an update request."""
        decision = self._adapter.compiler.policy_engine.validate_update(
            request, ctx
        )

        model_class = self._adapter.compiler.model_map.get(request.model)
        if model_class is None:
            raise ValueError(f"Model not found: {request.model}")

        pk_field = self._adapter.compiler._get_primary_key_field(model_class)

        return CompiledQuery(
            query={
                "model_class": model_class,
                "pk_field": pk_field,
                "pk_value": request.id,
                "data": request.data,
            },
            request=request,
            select_fields=decision.allowed_fields,
            injected_filters=decision.injected_filters,
            policy_decisions=decision.decisions,
        )

    def compile_delete(
        self,
        request: DeleteRequest,
        ctx: RunContext,
        policy: Policy,  # noqa: ARG002
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """Compile a delete request."""
        decision = self._adapter.compiler.policy_engine.validate_delete(
            request, ctx
        )

        model_class = self._adapter.compiler.model_map.get(request.model)
        if model_class is None:
            raise ValueError(f"Model not found: {request.model}")

        # Check for soft delete field
        model_meta = schema.get_model(request.model)
        soft_delete_field = None
        if model_meta and "deleted_at" in model_meta.fields:
            soft_delete_field = "deleted_at"

        pk_field = self._adapter.compiler._get_primary_key_field(model_class)

        return CompiledQuery(
            query={
                "model_class": model_class,
                "pk_field": pk_field,
                "pk_value": request.id,
                "soft_delete_field": soft_delete_field,
                "hard": request.hard,
            },
            request=request,
            select_fields=decision.allowed_fields,
            injected_filters=decision.injected_filters,
            policy_decisions=decision.decisions,
        )

    def compile_bulk_update(
        self,
        request: BulkUpdateRequest,
        ctx: RunContext,
        policy: Policy,  # noqa: ARG002
        schema: SchemaMetadata,  # noqa: ARG002
    ) -> CompiledQuery:
        """Compile a bulk update request."""
        decision = self._adapter.compiler.policy_engine.validate_bulk_update(
            request, ctx
        )

        model_class = self._adapter.compiler.model_map.get(request.model)
        if model_class is None:
            raise ValueError(f"Model not found: {request.model}")

        pk_field = self._adapter.compiler._get_primary_key_field(model_class)

        return CompiledQuery(
            query={
                "model_class": model_class,
                "pk_field": pk_field,
                "pk_values": request.ids,
                "data": request.data,
            },
            request=request,
            select_fields=decision.allowed_fields,
            injected_filters=decision.injected_filters,
            policy_decisions=decision.decisions,
        )

    # =========================================================================
    # EXECUTION METHODS (ASYNC)
    # =========================================================================

    async def execute_create(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,  # noqa: ARG002
    ) -> CreateResult:
        """Execute create asynchronously."""
        query_info = compiled.query
        model_class = query_info["model_class"]
        data = query_info["data"]

        # Create the instance
        instance = await model_class.create(**data)

        # Get the primary key value
        pk_field = self._adapter.compiler._get_primary_key_field(model_class)
        pk_value = getattr(instance, pk_field)

        # Convert to dict
        request = compiled.request
        if not isinstance(request, CreateRequest):
            raise ValueError("Expected CreateRequest")

        result_data = self._adapter._row_to_dict(
            instance, compiled.select_fields, request.model
        )

        return CreateResult(
            data=result_data,
            id=pk_value,
            success=True,
        )

    async def execute_update(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,  # noqa: ARG002
    ) -> UpdateResult:
        """Execute update asynchronously."""
        query_info = compiled.query
        model_class = query_info["model_class"]
        pk_field = query_info["pk_field"]
        pk_value = query_info["pk_value"]
        data = query_info["data"]

        # Build update query
        queryset = model_class.filter(**{pk_field: pk_value})

        # Apply scope filters
        for f in compiled.injected_filters:
            queryset = queryset.filter(**{f.field: f.value})

        updated_count = await queryset.update(**data)

        if updated_count == 0:
            return UpdateResult(data=None, success=True, found=False)

        # Fetch the updated instance
        instance = await model_class.get_or_none(**{pk_field: pk_value})

        if instance is None:
            return UpdateResult(data=None, success=True, found=False)

        request = compiled.request
        if not isinstance(request, UpdateRequest):
            raise ValueError("Expected UpdateRequest")

        result_data = self._adapter._row_to_dict(
            instance, compiled.select_fields, request.model
        )

        return UpdateResult(data=result_data, success=True, found=True)

    async def execute_delete(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,  # noqa: ARG002
    ) -> DeleteResult:
        """Execute delete asynchronously."""
        query_info = compiled.query
        model_class = query_info["model_class"]
        pk_field = query_info["pk_field"]
        pk_value = query_info["pk_value"]
        soft_delete_field = query_info.get("soft_delete_field")
        hard = query_info.get("hard", False)

        # Build query
        queryset = model_class.filter(**{pk_field: pk_value})

        # Apply scope filters
        for f in compiled.injected_filters:
            queryset = queryset.filter(**{f.field: f.value})

        if soft_delete_field and not hard:
            # Soft delete: set deleted_at timestamp
            deleted_count = await queryset.update(**{soft_delete_field: datetime.utcnow()})

            return DeleteResult(
                success=True,
                found=deleted_count > 0,
                soft_deleted=True,
            )
        else:
            # Hard delete
            deleted_count = await queryset.delete()

            return DeleteResult(
                success=True,
                found=deleted_count > 0,
                soft_deleted=False,
            )

    async def execute_bulk_update(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,  # noqa: ARG002
    ) -> BulkUpdateResult:
        """Execute bulk update asynchronously."""
        query_info = compiled.query
        model_class = query_info["model_class"]
        pk_field = query_info["pk_field"]
        pk_values = query_info["pk_values"]
        data = query_info["data"]

        # Build update query with IN clause
        queryset = model_class.filter(**{f"{pk_field}__in": pk_values})

        # Apply scope filters
        for f in compiled.injected_filters:
            queryset = queryset.filter(**{f.field: f.value})

        updated_count = await queryset.update(**data)

        return BulkUpdateResult(
            updated_count=updated_count,
            success=True,
        )
