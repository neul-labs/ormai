# Custom Tools Guide

This guide covers building domain-specific tools that extend OrmAI's capabilities.

## Why Custom Tools?

Generic tools (query, get, create, update, delete) are powerful but sometimes you need:

- **Business logic** - Validation, calculations, side effects
- **Multi-step operations** - Workflows spanning multiple models
- **Abstraction** - Hide complexity from agents
- **Safety** - Constrain what agents can do

## Basic Custom Tool

### Structure

```python
from ormai.tools import Tool, ToolResult
from ormai.core import RunContext

class CancelOrderTool(Tool):
    name = "cancel_order"
    description = "Cancel an order and process refund"

    async def execute(
        self,
        ctx: RunContext,
        order_id: int,
        reason: str,
    ) -> ToolResult:
        # Implementation here
        ...
```

### Complete Example

```python
class CancelOrderTool(Tool):
    name = "cancel_order"
    description = "Cancel an order and process refund if applicable"

    def __init__(self, toolset, refund_service):
        self.toolset = toolset
        self.refund_service = refund_service

    async def execute(
        self,
        ctx: RunContext,
        order_id: int,
        reason: str,
    ) -> ToolResult:
        # Get the order
        order_result = await self.toolset.get(
            ctx,
            model="Order",
            id=order_id,
        )

        if not order_result.success:
            return ToolResult(
                success=False,
                error=f"Order {order_id} not found",
            )

        order = order_result.data

        # Validate cancellation
        if order["status"] == "shipped":
            return ToolResult(
                success=False,
                error="Cannot cancel shipped orders",
            )

        if order["status"] == "cancelled":
            return ToolResult(
                success=False,
                error="Order already cancelled",
            )

        # Update order status
        await self.toolset.update(
            ctx,
            model="Order",
            id=order_id,
            data={
                "status": "cancelled",
                "cancel_reason": reason,
                "cancelled_at": datetime.now().isoformat(),
            },
        )

        # Process refund if paid
        refund_id = None
        if order["payment_status"] == "paid":
            refund_id = await self.refund_service.process(
                order_id=order_id,
                amount=order["total"],
            )

        return ToolResult(
            success=True,
            data={
                "order_id": order_id,
                "status": "cancelled",
                "refund_id": refund_id,
            },
        )
```

## Tool Parameters

### Defining Parameters

```python
from pydantic import BaseModel, Field

class TransferFundsParams(BaseModel):
    from_account_id: str = Field(..., description="Source account ID")
    to_account_id: str = Field(..., description="Destination account ID")
    amount: int = Field(..., gt=0, description="Amount in cents")
    memo: str | None = Field(None, description="Transfer memo")

class TransferFundsTool(Tool):
    name = "transfer_funds"
    description = "Transfer funds between accounts"
    parameters = TransferFundsParams

    async def execute(
        self,
        ctx: RunContext,
        from_account_id: str,
        to_account_id: str,
        amount: int,
        memo: str | None = None,
    ) -> ToolResult:
        ...
```

### Auto-Generated Schema

Parameters are exposed to LLMs:

```python
schema = tool.get_schema()
# {
#     "name": "transfer_funds",
#     "description": "Transfer funds between accounts",
#     "parameters": {
#         "type": "object",
#         "properties": {
#             "from_account_id": {"type": "string", "description": "Source account ID"},
#             "to_account_id": {"type": "string", "description": "Destination account ID"},
#             "amount": {"type": "integer", "minimum": 1, "description": "Amount in cents"},
#             "memo": {"type": "string", "description": "Transfer memo"}
#         },
#         "required": ["from_account_id", "to_account_id", "amount"]
#     }
# }
```

## Multi-Step Operations

### Order Fulfillment Example

```python
class FulfillOrderTool(Tool):
    name = "fulfill_order"
    description = "Process order fulfillment including inventory and shipping"

    async def execute(
        self,
        ctx: RunContext,
        order_id: int,
        tracking_number: str,
    ) -> ToolResult:
        # Get order with items
        order = await self.toolset.get(
            ctx,
            model="Order",
            id=order_id,
            include=[{"relation": "items"}],
        )

        if not order.success:
            return ToolResult(success=False, error="Order not found")

        # Start transaction
        async with self.adapter.transaction(ctx):
            # Update inventory for each item
            for item in order.data["items"]:
                await self.toolset.update(
                    ctx,
                    model="Inventory",
                    id=item["product_id"],
                    data={
                        "quantity": {"$decrement": item["quantity"]},
                    },
                )

            # Create shipment
            shipment = await self.toolset.create(
                ctx,
                model="Shipment",
                data={
                    "order_id": order_id,
                    "tracking_number": tracking_number,
                    "status": "shipped",
                },
            )

            # Update order status
            await self.toolset.update(
                ctx,
                model="Order",
                id=order_id,
                data={
                    "status": "shipped",
                    "shipment_id": shipment.data["id"],
                },
            )

        return ToolResult(
            success=True,
            data={
                "order_id": order_id,
                "shipment_id": shipment.data["id"],
                "tracking_number": tracking_number,
            },
        )
```

## Read-Only Domain Tools

### Analytics Tool

```python
class OrderAnalyticsTool(Tool):
    name = "order_analytics"
    description = "Get order analytics for a time period"

    async def execute(
        self,
        ctx: RunContext,
        start_date: str,
        end_date: str,
        group_by: str = "day",
    ) -> ToolResult:
        # Get aggregated data
        result = await self.toolset.aggregate(
            ctx,
            model="Order",
            filters=[
                {"field": "created_at", "op": "gte", "value": start_date},
                {"field": "created_at", "op": "lt", "value": end_date},
                {"field": "status", "op": "neq", "value": "cancelled"},
            ],
            aggregations=[
                {"function": "count", "alias": "order_count"},
                {"function": "sum", "field": "total", "alias": "revenue"},
                {"function": "avg", "field": "total", "alias": "avg_order_value"},
            ],
            group_by=[f"date_trunc('{group_by}', created_at)"],
        )

        return ToolResult(
            success=True,
            data={
                "period": {"start": start_date, "end": end_date},
                "metrics": result.data,
            },
        )
```

## Validation and Guards

### Input Validation

```python
class UpdatePricingTool(Tool):
    name = "update_pricing"
    description = "Update product pricing"

    async def execute(
        self,
        ctx: RunContext,
        product_id: str,
        new_price: int,
    ) -> ToolResult:
        # Validate price
        if new_price < 0:
            return ToolResult(
                success=False,
                error="Price cannot be negative",
            )

        # Get current price
        product = await self.toolset.get(ctx, model="Product", id=product_id)

        if not product.success:
            return ToolResult(success=False, error="Product not found")

        old_price = product.data["price"]

        # Guard against extreme changes
        change_percent = abs(new_price - old_price) / old_price * 100
        if change_percent > 50:
            return ToolResult(
                success=False,
                error=f"Price change of {change_percent:.0f}% exceeds 50% limit",
                data={"requires_approval": True},
            )

        # Apply update
        await self.toolset.update(
            ctx,
            model="Product",
            id=product_id,
            data={"price": new_price},
        )

        return ToolResult(
            success=True,
            data={
                "product_id": product_id,
                "old_price": old_price,
                "new_price": new_price,
            },
        )
```

## External Service Integration

```python
class SendNotificationTool(Tool):
    name = "send_notification"
    description = "Send notification to a user"

    def __init__(self, toolset, notification_service):
        self.toolset = toolset
        self.notification_service = notification_service

    async def execute(
        self,
        ctx: RunContext,
        user_id: str,
        message: str,
        channel: str = "email",
    ) -> ToolResult:
        # Get user
        user = await self.toolset.get(ctx, model="User", id=user_id)

        if not user.success:
            return ToolResult(success=False, error="User not found")

        # Send via external service
        try:
            notification_id = await self.notification_service.send(
                recipient=user.data["email"] if channel == "email" else user.data["phone"],
                message=message,
                channel=channel,
            )
        except NotificationError as e:
            return ToolResult(success=False, error=str(e))

        # Log notification
        await self.toolset.create(
            ctx,
            model="NotificationLog",
            data={
                "user_id": user_id,
                "message": message,
                "channel": channel,
                "external_id": notification_id,
            },
        )

        return ToolResult(
            success=True,
            data={"notification_id": notification_id},
        )
```

## Registering Custom Tools

```python
from ormai.tools import ToolRegistry

registry = ToolRegistry()

# Register built-in tools
registry.register(QueryTool(adapter, policy))
registry.register(GetTool(adapter, policy))

# Register custom tools
registry.register(CancelOrderTool(toolset, refund_service))
registry.register(FulfillOrderTool(toolset, adapter))
registry.register(OrderAnalyticsTool(toolset))
```

## Code Generation

Generate tool stubs from your schema:

```python
from ormai.codegen import DomainToolGenerator

generator = DomainToolGenerator(
    schema=schema,
    policy=policy,
    output_dir="./generated/tools",
)

generator.generate_all()
```

Generated stub:

```python
# ./generated/tools/order_tools.py
from ormai.tools import Tool, ToolResult

class ProcessOrderTool(Tool):
    """Process an order through the fulfillment workflow."""

    name = "process_order"
    description = "Process an order through the fulfillment workflow"

    async def execute(
        self,
        ctx: RunContext,
        order_id: int,
    ) -> ToolResult:
        # TODO: Implement business logic
        raise NotImplementedError()
```

## Testing Custom Tools

```python
import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def cancel_order_tool():
    toolset = AsyncMock()
    refund_service = AsyncMock()
    return CancelOrderTool(toolset, refund_service)

async def test_cancel_order_success(cancel_order_tool):
    cancel_order_tool.toolset.get.return_value = ToolResult(
        success=True,
        data={"id": 1, "status": "pending", "payment_status": "paid", "total": 5000},
    )
    cancel_order_tool.refund_service.process.return_value = "refund-123"

    ctx = RunContext(principal=Principal(tenant_id="t", user_id="u"), db=None)
    result = await cancel_order_tool.execute(ctx, order_id=1, reason="Customer request")

    assert result.success
    assert result.data["refund_id"] == "refund-123"

async def test_cancel_shipped_order_fails(cancel_order_tool):
    cancel_order_tool.toolset.get.return_value = ToolResult(
        success=True,
        data={"id": 1, "status": "shipped"},
    )

    ctx = RunContext(principal=Principal(tenant_id="t", user_id="u"), db=None)
    result = await cancel_order_tool.execute(ctx, order_id=1, reason="Test")

    assert not result.success
    assert "shipped" in result.error
```

## Best Practices

1. **Single responsibility** - Each tool does one thing well

2. **Clear descriptions** - Help LLMs understand when to use each tool

3. **Validate inputs** - Check parameters before operations

4. **Use transactions** - Group related database operations

5. **Return meaningful errors** - Help agents recover from failures

6. **Log operations** - Use audit middleware for custom tools

7. **Test thoroughly** - Unit test all edge cases

## Next Steps

- [Code Generation](code-generation.md) - Auto-generate tool stubs
- [Evaluation](evaluation.md) - Test tool behavior
- [MCP Integration](../api-reference/mcp.md) - Expose tools via MCP
