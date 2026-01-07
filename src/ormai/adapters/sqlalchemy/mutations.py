"""
Mutation execution methods for SQLAlchemy adapter.

This module contains the mutation compilation and execution logic
(create, update, delete, bulk_update).
"""

from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from ormai.adapters.base import CompiledQuery
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
    from ormai.adapters.sqlalchemy.adapter import SQLAlchemyAdapter


class MutationExecutor:
    """
    Handles mutation compilation and execution for SQLAlchemy adapter.

    Contains methods for compiling and executing create, update,
    delete, and bulk_update operations.
    """

    def __init__(self, adapter: "SQLAlchemyAdapter") -> None:
        """Initialize with reference to parent adapter."""
        self._adapter = adapter

    # =========================================================================
    # COMPILATION METHODS
    # =========================================================================

    def compile_create(
        self,
        request: CreateRequest,
        ctx: Any,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """Compile a create request."""
        decision = self._adapter.compiler.policy_engine.validate_create(
            request, ctx
        )

        model_class = self._adapter.model_map.get(request.model)
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
        ctx: Any,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """Compile an update request."""
        decision = self._adapter.compiler.policy_engine.validate_update(
            request, ctx
        )

        model_class = self._adapter.model_map.get(request.model)
        if model_class is None:
            raise ValueError(f"Model not found: {request.model}")

        pk_column = self._adapter.compiler._get_primary_key_column(model_class)

        return CompiledQuery(
            query={
                "model_class": model_class,
                "pk_column": pk_column,
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
        ctx: Any,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """Compile a delete request."""
        decision = self._adapter.compiler.policy_engine.validate_delete(
            request, ctx
        )

        model_class = self._adapter.model_map.get(request.model)
        if model_class is None:
            raise ValueError(f"Model not found: {request.model}")

        model_meta = schema.get_model(request.model)
        soft_delete_field = None
        if model_meta:
            # Check if the model has a deleted_at field for soft deletes
            if "deleted_at" in model_meta.fields:
                soft_delete_field = "deleted_at"

        pk_column = self._adapter.compiler._get_primary_key_column(model_class)

        return CompiledQuery(
            query={
                "model_class": model_class,
                "pk_column": pk_column,
                "pk_value": request.id,
                "soft_delete_field": soft_delete_field,
            },
            request=request,
            select_fields=decision.allowed_fields,
            injected_filters=decision.injected_filters,
            policy_decisions=decision.decisions,
        )

    def compile_bulk_update(
        self,
        request: BulkUpdateRequest,
        ctx: Any,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """Compile a bulk update request."""
        decision = self._adapter.compiler.policy_engine.validate_bulk_update(
            request, ctx
        )

        model_class = self._adapter.model_map.get(request.model)
        if model_class is None:
            raise ValueError(f"Model not found: {request.model}")

        pk_column = self._adapter.compiler._get_primary_key_column(model_class)

        return CompiledQuery(
            query={
                "model_class": model_class,
                "pk_column": pk_column,
                "pk_values": request.ids,
                "data": request.data,
            },
            request=request,
            select_fields=decision.allowed_fields,
            injected_filters=decision.injected_filters,
            policy_decisions=decision.decisions,
        )

    # =========================================================================
    # EXECUTION METHODS
    # =========================================================================

    def execute_create(
        self,
        compiled: CompiledQuery,
        ctx: Any,
    ) -> CreateResult:
        """Execute a create request."""
        if self._adapter.is_async:
            from sqlalchemy.ext.asyncio import AsyncSession

            session: AsyncSession = ctx.db
            return self._execute_create_async(session, compiled)
        else:
            session: Session = ctx.db
            return self._execute_create_sync(session, compiled)

    def _execute_create_sync(
        self,
        session: Session,
        compiled: CompiledQuery,
    ) -> CreateResult:
        """Execute create synchronously."""
        query_info = compiled.query
        model_class = query_info["model_class"]
        data = query_info["data"]

        # Create the instance
        instance = model_class(**data)
        session.add(instance)
        session.flush()

        # Get the primary key value
        pk_column = self._adapter.compiler._get_primary_key_column(model_class)
        pk_value = getattr(instance, pk_column)

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

    async def _execute_create_async(
        self,
        session: AsyncSession,
        compiled: CompiledQuery,
    ) -> CreateResult:
        """Execute create asynchronously."""
        query_info = compiled.query
        model_class = query_info["model_class"]
        data = query_info["data"]

        # Create the instance
        instance = model_class(**data)
        session.add(instance)
        await session.flush()

        # Get the primary key value
        pk_column = self._adapter.compiler._get_primary_key_column(model_class)
        pk_value = getattr(instance, pk_column)

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

    def execute_update(
        self,
        compiled: CompiledQuery,
        ctx: Any,
    ) -> UpdateResult:
        """Execute an update request."""
        if self._adapter.is_async:
            from sqlalchemy.ext.asyncio import AsyncSession

            session: AsyncSession = ctx.db
            return self._execute_update_async(session, compiled)
        else:
            session: Session = ctx.db
            return self._execute_update_sync(session, compiled)

    def _execute_update_sync(
        self,
        session: Session,
        compiled: CompiledQuery,
    ) -> UpdateResult:
        """Execute update synchronously."""
        from sqlalchemy import select, update

        query_info = compiled.query
        model_class = query_info["model_class"]
        pk_column = query_info["pk_column"]
        pk_value = query_info["pk_value"]
        data = query_info["data"]

        pk_attr = getattr(model_class, pk_column)
        stmt = update(model_class).where(pk_attr == pk_value).values(**data)
        stmt = self._adapter._apply_scope_filters(
            stmt, model_class, compiled.injected_filters
        )

        result = session.execute(stmt)
        session.flush()

        if result.rowcount == 0:
            return UpdateResult(data=None, success=True, found=False)

        fetch_stmt = select(model_class).where(pk_attr == pk_value)
        row = session.execute(fetch_stmt).scalars().first()

        if row:
            return self._build_update_result(row, compiled)

        return UpdateResult(data=None, success=True, found=False)

    async def _execute_update_async(
        self,
        session: AsyncSession,
        compiled: CompiledQuery,
    ) -> UpdateResult:
        """Execute update asynchronously."""
        from sqlalchemy import select, update

        query_info = compiled.query
        model_class = query_info["model_class"]
        pk_column = query_info["pk_column"]
        pk_value = query_info["pk_value"]
        data = query_info["data"]

        pk_attr = getattr(model_class, pk_column)
        stmt = update(model_class).where(pk_attr == pk_value).values(**data)
        stmt = self._adapter._apply_scope_filters(
            stmt, model_class, compiled.injected_filters
        )

        result = await session.execute(stmt)
        await session.flush()

        if result.rowcount == 0:
            return UpdateResult(data=None, success=True, found=False)

        fetch_stmt = select(model_class).where(pk_attr == pk_value)
        row_result = await session.execute(fetch_stmt)
        row = row_result.scalars().first()

        if row:
            return self._build_update_result(row, compiled)

        return UpdateResult(data=None, success=True, found=False)

    def _build_update_result(
        self,
        row: Any,
        compiled: CompiledQuery,
    ) -> UpdateResult:
        """Build an UpdateResult from a row."""
        request = compiled.request
        if not isinstance(request, UpdateRequest):
            raise ValueError("Expected UpdateRequest")

        result_data = self._adapter._row_to_dict(
            row, compiled.select_fields, request.model
        )
        return UpdateResult(data=result_data, success=True, found=True)

    def execute_delete(
        self,
        compiled: CompiledQuery,
        ctx: Any,
    ) -> DeleteResult:
        """Execute a delete request."""
        if self._adapter.is_async:
            from sqlalchemy.ext.asyncio import AsyncSession

            session: AsyncSession = ctx.db
            return self._execute_delete_async(session, compiled)
        else:
            session: Session = ctx.db
            return self._execute_delete_sync(session, compiled)

    def _execute_delete_sync(
        self,
        session: Session,
        compiled: CompiledQuery,
    ) -> DeleteResult:
        """Execute delete synchronously."""
        from datetime import datetime

        from sqlalchemy import delete, update

        query_info = compiled.query
        model_class = query_info["model_class"]
        pk_column = query_info["pk_column"]
        pk_value = query_info["pk_value"]
        soft_delete_field = query_info.get("soft_delete_field")

        pk_attr = getattr(model_class, pk_column)

        if soft_delete_field:
            stmt = update(model_class).where(pk_attr == pk_value).values(
                **{soft_delete_field: datetime.utcnow()}
            )
        else:
            stmt = delete(model_class).where(pk_attr == pk_value)

        stmt = self._adapter._apply_scope_filters(
            stmt, model_class, compiled.injected_filters
        )

        result = session.execute(stmt)
        session.flush()

        return DeleteResult(
            success=True,
            found=result.rowcount > 0,
            soft_deleted=soft_delete_field is not None,
        )

    async def _execute_delete_async(
        self,
        session: AsyncSession,
        compiled: CompiledQuery,
    ) -> DeleteResult:
        """Execute delete asynchronously."""
        from datetime import datetime

        from sqlalchemy import delete, update

        query_info = compiled.query
        model_class = query_info["model_class"]
        pk_column = query_info["pk_column"]
        pk_value = query_info["pk_value"]
        soft_delete_field = query_info.get("soft_delete_field")

        pk_attr = getattr(model_class, pk_column)

        if soft_delete_field:
            stmt = update(model_class).where(pk_attr == pk_value).values(
                **{soft_delete_field: datetime.utcnow()}
            )
        else:
            stmt = delete(model_class).where(pk_attr == pk_value)

        stmt = self._adapter._apply_scope_filters(
            stmt, model_class, compiled.injected_filters
        )

        result = await session.execute(stmt)
        await session.flush()

        return DeleteResult(
            success=True,
            found=result.rowcount > 0,
            soft_deleted=soft_delete_field is not None,
        )

    def execute_bulk_update(
        self,
        compiled: CompiledQuery,
        ctx: Any,
    ) -> BulkUpdateResult:
        """Execute a bulk update request."""
        if self._adapter.is_async:
            from sqlalchemy.ext.asyncio import AsyncSession

            session: AsyncSession = ctx.db
            return self._execute_bulk_update_async(session, compiled)
        else:
            session: Session = ctx.db
            return self._execute_bulk_update_sync(session, compiled)

    def _execute_bulk_update_sync(
        self,
        session: Session,
        compiled: CompiledQuery,
    ) -> BulkUpdateResult:
        """Execute bulk update synchronously."""
        from sqlalchemy import update

        query_info = compiled.query
        model_class = query_info["model_class"]
        pk_column = query_info["pk_column"]
        pk_values = query_info["pk_values"]
        data = query_info["data"]

        pk_attr = getattr(model_class, pk_column)
        stmt = update(model_class).where(pk_attr.in_(pk_values)).values(**data)
        stmt = self._adapter._apply_scope_filters(
            stmt, model_class, compiled.injected_filters
        )

        result = session.execute(stmt)
        session.flush()

        return BulkUpdateResult(
            updated_count=result.rowcount,
            success=True,
        )

    async def _execute_bulk_update_async(
        self,
        session: AsyncSession,
        compiled: CompiledQuery,
    ) -> BulkUpdateResult:
        """Execute bulk update asynchronously."""
        from sqlalchemy import update

        query_info = compiled.query
        model_class = query_info["model_class"]
        pk_column = query_info["pk_column"]
        pk_values = query_info["pk_values"]
        data = query_info["data"]

        pk_attr = getattr(model_class, pk_column)
        stmt = update(model_class).where(pk_attr.in_(pk_values)).values(**data)
        stmt = self._adapter._apply_scope_filters(
            stmt, model_class, compiled.injected_filters
        )

        result = await session.execute(stmt)
        await session.flush()

        return BulkUpdateResult(
            updated_count=result.rowcount,
            success=True,
        )
