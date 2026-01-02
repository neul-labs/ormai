# LangGraph Integration

This guide covers integrating OrmAI with LangGraph for building sophisticated AI agents with database access.

## Overview

LangGraph enables building stateful, multi-step AI agents. OrmAI provides safe database tools that these agents can use.

## Installation

```bash
pip install ormai langgraph langchain-anthropic
```

## Basic Integration

### Setup

```python
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage

from ormai.quickstart import mount_sqlalchemy
from ormai.core import Principal, RunContext
from ormai.integrations.langgraph import create_langgraph_tools

# Setup OrmAI
toolset = mount_sqlalchemy(engine=engine, base=Base, policy=policy)

# Create LangGraph-compatible tools
tools = create_langgraph_tools(toolset)

# Setup LLM
llm = ChatAnthropic(model="claude-sonnet-4-20250514").bind_tools(tools)
```

### Create Agent Graph

```python
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    context: RunContext

def should_continue(state: AgentState) -> str:
    messages = state["messages"]
    last_message = messages[-1]

    if last_message.tool_calls:
        return "tools"
    return END

async def call_model(state: AgentState):
    messages = state["messages"]
    response = await llm.ainvoke(messages)
    return {"messages": [response]}

# Create tool node with context
tool_node = ToolNode(tools)

# Build graph
workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)

workflow.set_entry_point("agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        END: END,
    },
)
workflow.add_edge("tools", "agent")

agent = workflow.compile()
```

### Run Agent

```python
async def run_agent(query: str, tenant_id: str, user_id: str):
    ctx = RunContext(
        principal=Principal(tenant_id=tenant_id, user_id=user_id),
        db=session,
    )

    result = await agent.ainvoke({
        "messages": [HumanMessage(content=query)],
        "context": ctx,
    })

    return result["messages"][-1].content

# Example
response = await run_agent(
    "What are my pending orders and their total value?",
    tenant_id="acme-corp",
    user_id="user-123",
)
print(response)
```

## Tool Conversion

### Automatic Conversion

```python
from ormai.integrations.langgraph import create_langgraph_tools

# Convert all OrmAI tools to LangGraph format
tools = create_langgraph_tools(
    toolset,
    include=["query", "get", "aggregate"],  # Optional: filter tools
)
```

### Manual Tool Definition

```python
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

class QueryInput(BaseModel):
    model: str = Field(description="The database model to query")
    filters: list[dict] = Field(default=[], description="Filter conditions")
    limit: int = Field(default=10, description="Maximum results")

async def query_database(
    model: str,
    filters: list[dict] = [],
    limit: int = 10,
) -> dict:
    ctx = get_current_context()  # Your context management
    result = await toolset.query(
        ctx,
        model=model,
        filters=filters,
        limit=limit,
    )
    return result.data

query_tool = StructuredTool.from_function(
    func=query_database,
    name="query_database",
    description="Query records from the database",
    args_schema=QueryInput,
)
```

## Context Management

### Thread-Safe Context

```python
from contextvars import ContextVar

_current_context: ContextVar[RunContext] = ContextVar("ormai_context")

def set_context(ctx: RunContext):
    _current_context.set(ctx)

def get_context() -> RunContext:
    return _current_context.get()

# In your tool implementations
async def query_tool_impl(**kwargs):
    ctx = get_context()
    return await toolset.query(ctx, **kwargs)
```

### State-Based Context

```python
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    tenant_id: str
    user_id: str
    db_session: Any

async def tool_node_with_context(state: AgentState):
    ctx = RunContext(
        principal=Principal(
            tenant_id=state["tenant_id"],
            user_id=state["user_id"],
        ),
        db=state["db_session"],
    )

    # Process tool calls with context
    messages = state["messages"]
    last_message = messages[-1]

    results = []
    for tool_call in last_message.tool_calls:
        result = await execute_tool(tool_call, ctx)
        results.append(result)

    return {"messages": results}
```

## Multi-Agent Setup

### Specialized Agents

```python
# Query agent - read-only access
query_tools = create_langgraph_tools(
    toolset,
    include=["describe_schema", "query", "get", "aggregate"],
)
query_agent = create_agent(query_tools)

# Admin agent - full access
admin_tools = create_langgraph_tools(
    toolset,
    include=["query", "get", "create", "update", "delete"],
)
admin_agent = create_agent(admin_tools)

# Router
def route_to_agent(state):
    if requires_write(state["messages"]):
        return "admin"
    return "query"

workflow = StateGraph(AgentState)
workflow.add_node("query_agent", query_agent)
workflow.add_node("admin_agent", admin_agent)
workflow.add_conditional_edges(
    "router",
    route_to_agent,
)
```

### Supervisor Pattern

```python
from langgraph.prebuilt import create_supervisor

# Create supervisor that delegates to specialized agents
supervisor = create_supervisor(
    agents=["data_analyst", "data_modifier"],
    system_prompt="""You are a supervisor managing database agents.
    - Use data_analyst for queries and analysis
    - Use data_modifier for creating/updating records
    """,
)
```

## Streaming

### Stream Tool Results

```python
async def stream_agent(query: str, ctx: RunContext):
    async for event in agent.astream_events(
        {"messages": [HumanMessage(content=query)], "context": ctx},
        version="v1",
    ):
        if event["event"] == "on_tool_end":
            yield {
                "type": "tool_result",
                "tool": event["name"],
                "data": event["data"]["output"],
            }
        elif event["event"] == "on_chat_model_stream":
            yield {
                "type": "token",
                "content": event["data"]["chunk"].content,
            }
```

## Error Handling

### Graceful Degradation

```python
from ormai.core import OrmAIError

async def safe_tool_execution(tool_call, ctx):
    try:
        return await execute_tool(tool_call, ctx)
    except OrmAIError as e:
        return ToolMessage(
            content=f"Database error: {e.message}",
            tool_call_id=tool_call["id"],
            status="error",
        )

class RobustToolNode:
    def __init__(self, tools):
        self.tools = {t.name: t for t in tools}

    async def __call__(self, state: AgentState):
        ctx = build_context(state)
        last_message = state["messages"][-1]

        results = []
        for tool_call in last_message.tool_calls:
            result = await safe_tool_execution(tool_call, ctx)
            results.append(result)

        return {"messages": results}
```

## Memory and Persistence

### Checkpointing

```python
from langgraph.checkpoint.sqlite import SqliteSaver

# Persist agent state
memory = SqliteSaver.from_conn_string(":memory:")

agent = workflow.compile(checkpointer=memory)

# Resume from checkpoint
config = {"configurable": {"thread_id": "user-session-123"}}
result = await agent.ainvoke(
    {"messages": [HumanMessage(content="Show my orders")]},
    config=config,
)
```

## Complete Example

```python
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from ormai.quickstart import mount_sqlalchemy
from ormai.core import Principal, RunContext
from ormai.integrations.langgraph import create_langgraph_tools

# Setup
engine = create_engine("postgresql://localhost/mydb")
toolset = mount_sqlalchemy(engine, Base, policy)
tools = create_langgraph_tools(toolset)
llm = ChatAnthropic(model="claude-sonnet-4-20250514").bind_tools(tools)

# System prompt
SYSTEM_PROMPT = """You are a helpful assistant with access to a database.
You can query orders, users, and products. Always respect user permissions.
When showing data, format it clearly. Ask for clarification if needed."""

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    principal: Principal

async def agent_node(state: AgentState):
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(state["messages"])
    response = await llm.ainvoke(messages)
    return {"messages": [response]}

def should_continue(state):
    if state["messages"][-1].tool_calls:
        return "tools"
    return END

# Build
workflow = StateGraph(AgentState)
workflow.add_node("agent", agent_node)
workflow.add_node("tools", ToolNode(tools))
workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", should_continue)
workflow.add_edge("tools", "agent")

agent = workflow.compile()

# Run
async def chat(user_input: str, tenant_id: str, user_id: str):
    principal = Principal(tenant_id=tenant_id, user_id=user_id)

    result = await agent.ainvoke({
        "messages": [HumanMessage(content=user_input)],
        "principal": principal,
    })

    return result["messages"][-1].content

# Usage
response = await chat(
    "What's the total revenue from completed orders this month?",
    tenant_id="acme-corp",
    user_id="analyst-1",
)
```

## Best Practices

1. **Limit tool access** - Only expose needed tools to each agent

2. **Use read-only by default** - Give write access only when necessary

3. **Handle errors gracefully** - Don't let database errors crash agents

4. **Log everything** - Use audit middleware for visibility

5. **Test with invariants** - Use eval harness for agent testing

## Next Steps

- [FastAPI Integration](fastapi.md) - HTTP API for agents
- [Custom Tools](../guides/custom-tools.md) - Build domain-specific tools
- [Evaluation](../guides/evaluation.md) - Test agent behavior
