"""
OrmAI Integrations Module.

Provides integrations with popular frameworks and libraries.
"""

# Lazy imports to avoid requiring all dependencies

__all__ = [
    "get_fastapi_integration",
    "get_langgraph_integration",
]


def get_fastapi_integration():
    """Get FastAPI integration utilities."""
    from ormai.integrations import fastapi
    return fastapi


def get_langgraph_integration():
    """Get LangGraph integration utilities."""
    from ormai.integrations import langgraph
    return langgraph
