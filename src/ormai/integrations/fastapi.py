"""
FastAPI integration for OrmAI.

Provides easy mounting of OrmAI tools as FastAPI endpoints.
"""

from collections.abc import Callable
from typing import Any

from ormai.core.context import Principal, RunContext
from ormai.tools.registry import ToolRegistry

try:
    from fastapi import APIRouter, Depends, HTTPException, Request
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


class ToolCallRequest(BaseModel):
    """Request body for tool calls."""

    name: str
    arguments: dict[str, Any]


class ToolCallResponse(BaseModel):
    """Response body for tool calls."""

    success: bool
    result: dict[str, Any] | None = None
    error: dict[str, str] | None = None


class OrmAIRouter:
    """
    FastAPI router for OrmAI tools.

    Provides endpoints for listing and calling OrmAI tools.

    Usage:
        from fastapi import FastAPI
        from ormai.integrations.fastapi import OrmAIRouter

        app = FastAPI()

        ormai_router = OrmAIRouter(
            toolset=toolset,
            get_principal=get_current_user,
            get_db=get_db_session,
        )

        app.include_router(ormai_router.router, prefix="/ormai")
    """

    def __init__(
        self,
        toolset: ToolRegistry,
        get_principal: Callable[..., Principal] | None = None,
        get_db: Callable[..., Any] | None = None,
        prefix: str = "",
    ) -> None:
        """
        Initialize the router.

        Args:
            toolset: The OrmAI tool registry
            get_principal: Dependency to get the current principal
            get_db: Dependency to get the database session
            prefix: Optional path prefix for routes
        """
        if not HAS_FASTAPI:
            raise ImportError(
                "FastAPI is not installed. Install with: pip install fastapi"
            )

        self.toolset = toolset
        self.get_principal = get_principal
        self.get_db = get_db
        self.router = APIRouter(prefix=prefix)

        self._setup_routes()

    def _setup_routes(self) -> None:
        """Set up the API routes."""

        @self.router.get("/tools")
        async def list_tools() -> list[dict[str, Any]]:
            """List all available tools with their schemas."""
            return self.toolset.get_schemas()

        @self.router.get("/tools/{name}")
        async def get_tool(name: str) -> dict[str, Any]:
            """Get a specific tool's schema."""
            if name not in self.toolset.tools:
                raise HTTPException(status_code=404, detail=f"Tool not found: {name}")
            return self.toolset.tools[name].get_schema()

        @self.router.post("/call")
        async def call_tool(
            request: ToolCallRequest,
            http_request: Request,
        ) -> ToolCallResponse:
            """Call a tool with the given arguments."""
            try:
                # Build context
                ctx = await self._build_context(http_request)

                # Execute tool
                result = await self.toolset.execute(
                    request.name,
                    request.arguments,
                    ctx,
                )

                return ToolCallResponse(
                    success=True,
                    result=result.model_dump(),
                )

            except Exception as e:
                return ToolCallResponse(
                    success=False,
                    error={
                        "type": type(e).__name__,
                        "message": str(e),
                    },
                )

        @self.router.post("/tools/{name}/call")
        async def call_tool_by_name(
            name: str,
            arguments: dict[str, Any],
            http_request: Request,
        ) -> ToolCallResponse:
            """Call a specific tool."""
            request = ToolCallRequest(name=name, arguments=arguments)
            return await call_tool(request, http_request)

    async def _build_context(self, request: Request) -> RunContext:
        """Build a RunContext from the HTTP request."""
        # Get principal
        if self.get_principal:
            if callable(self.get_principal):
                principal = self.get_principal(request)
                if hasattr(principal, "__await__"):
                    principal = await principal
            else:
                principal = Principal(tenant_id="default", user_id="anonymous")
        else:
            principal = Principal(tenant_id="default", user_id="anonymous")

        # Get database session
        db = None
        if self.get_db:
            if callable(self.get_db):
                db = self.get_db(request)
                if hasattr(db, "__await__"):
                    db = await db

        return RunContext(principal=principal, db=db)


def create_ormai_router(
    toolset: ToolRegistry,
    get_principal: Callable[..., Principal] | None = None,
    get_db: Callable[..., Any] | None = None,
    prefix: str = "/ormai",
) -> Any:
    """
    Create a FastAPI router for OrmAI tools.

    Usage:
        from fastapi import FastAPI
        from ormai.integrations.fastapi import create_ormai_router

        app = FastAPI()
        router = create_ormai_router(toolset)
        app.include_router(router)
    """
    ormai = OrmAIRouter(
        toolset=toolset,
        get_principal=get_principal,
        get_db=get_db,
        prefix=prefix,
    )
    return ormai.router


def mount_ormai(
    app: Any,
    toolset: ToolRegistry,
    prefix: str = "/ormai",
    **kwargs: Any,
) -> None:
    """
    Mount OrmAI tools on a FastAPI app.

    Usage:
        from fastapi import FastAPI
        from ormai.integrations.fastapi import mount_ormai

        app = FastAPI()
        mount_ormai(app, toolset)
    """
    router = create_ormai_router(toolset, prefix=prefix, **kwargs)
    app.include_router(router)
