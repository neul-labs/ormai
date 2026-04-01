"""
FastAPI application with OrmAI integration.
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session, init_db
from app.ormai_setup import ormai
from ormai.core.context import RunContext

# === Request/Response Models ===


class QueryRequest(BaseModel):
    model: str
    select: list[str] | None = None
    where: list[dict[str, Any]] | None = None
    order_by: list[dict[str, Any]] | None = None
    take: int = 25
    cursor: str | None = None
    include: list[dict[str, Any]] | None = None


class GetRequest(BaseModel):
    model: str
    id: Any
    select: list[str] | None = None
    include: list[dict[str, Any]] | None = None


class AggregateRequest(BaseModel):
    model: str
    operation: str
    field: str | None = None
    where: list[dict[str, Any]] | None = None


# === App Setup ===


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """Application lifespan handler."""
    # Initialize database on startup
    await init_db()
    yield


app = FastAPI(
    title="OrmAI Example",
    description="FastAPI + SQLAlchemy example with OrmAI",
    version="0.1.0",
    lifespan=lifespan,
)


# === Dependencies ===


async def get_context(
    session: AsyncSession = Depends(get_session),
    x_tenant_id: str = Header(default="default"),
    x_user_id: str = Header(default="anonymous"),
) -> RunContext:
    """Build OrmAI context from request headers."""
    return RunContext.create(
        tenant_id=x_tenant_id,
        user_id=x_user_id,
        db=session,
    )


# === Endpoints ===


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "ormai-example"}


@app.get("/schema")
async def get_schema(ctx: RunContext = Depends(get_context)):
    """Get the database schema."""
    result = await ormai.toolset.execute(
        "db.describe_schema",
        {},
        ctx,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    return result.data


@app.post("/query")
async def query(
    request: QueryRequest,
    ctx: RunContext = Depends(get_context),
):
    """Execute a query."""
    result = await ormai.toolset.execute(
        "db.query",
        request.model_dump(),
        ctx,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    return result.data


@app.post("/get")
async def get(
    request: GetRequest,
    ctx: RunContext = Depends(get_context),
):
    """Get a record by ID."""
    result = await ormai.toolset.execute(
        "db.get",
        request.model_dump(),
        ctx,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    return result.data


@app.post("/aggregate")
async def aggregate(
    request: AggregateRequest,
    ctx: RunContext = Depends(get_context),
):
    """Execute an aggregation."""
    result = await ormai.toolset.execute(
        "db.aggregate",
        request.model_dump(),
        ctx,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    return result.data


@app.get("/tools")
async def list_tools():
    """List available OrmAI tools."""
    return ormai.toolset.get_schemas()
