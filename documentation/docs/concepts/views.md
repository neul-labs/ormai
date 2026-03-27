# Views

Views are projection models that decouple API responses from ORM entities. They provide stable, policy-aligned interfaces for AI agents.

## Why Views?

ORM models often contain more than what agents should see:

- Internal fields (timestamps, flags)
- Sensitive data (passwords, tokens)
- Implementation details (foreign keys)

Views solve this by:

- Exposing only allowed fields
- Applying consistent transformations
- Providing stable schemas for LLM consumption
- Enabling multiple representations per model

## Creating Views

### Automatic View Generation

Generate views from your policy:

```python
from ormai.views import ViewFactory

factory = ViewFactory(schema=schema, policy=policy)

# Generate view for a model
UserView = factory.create_view("User")

# Use the view
user_data = UserView(
    id="u-123",
    name="Alice",
    email="a***@***.com",  # Masked per policy
)
```

### Manual View Definition

Define views explicitly:

```python
from ormai.views import BaseView
from pydantic import Field

class UserView(BaseView):
    id: str
    name: str
    email: str = Field(..., description="User's email (may be masked)")

    class Config:
        orm_model = "User"
        policy_aligned = True

class UserDetailView(UserView):
    """Extended view with more fields."""
    created_at: datetime
    order_count: int
```

## View Factory

The `ViewFactory` generates Pydantic models from schema and policy:

```python
from ormai.views import ViewFactory

factory = ViewFactory(
    schema=adapter.introspect(),
    policy=policy,
)

# Generate all views
views = factory.create_all_views()
# {"User": UserView, "Order": OrderView, ...}

# Generate with options
OrderView = factory.create_view(
    "Order",
    include_relations=["user", "items"],
    exclude_fields=["internal_notes"],
)
```

### View Options

```python
factory.create_view(
    "Order",
    name="OrderSummaryView",          # Custom view name
    include_fields=["id", "status"],  # Only these fields
    exclude_fields=["internal"],      # Exclude these
    include_relations=["user"],       # Include relations
    relation_depth=1,                 # Max relation nesting
    apply_redaction=True,             # Apply field masking
)
```

## Multiple Views Per Model

Create different views for different use cases:

```python
# List view - minimal fields
OrderListView = factory.create_view(
    "Order",
    name="OrderListView",
    include_fields=["id", "status", "total", "created_at"],
)

# Detail view - all fields with relations
OrderDetailView = factory.create_view(
    "Order",
    name="OrderDetailView",
    include_relations=["user", "items", "payments"],
    relation_depth=2,
)

# Admin view - includes internal fields
OrderAdminView = factory.create_view(
    "Order",
    name="OrderAdminView",
    include_fields=None,  # All fields
    apply_redaction=False,  # No masking for admins
)
```

## Using Views with Tools

Views integrate with tool responses:

```python
result = await toolset.query(
    ctx,
    model="Order",
    view="OrderListView",  # Use specific view
    ...
)

# Response is validated against OrderListView
```

### View Selection by Role

```python
def get_view_for_role(model: str, roles: list[str]) -> str:
    if "admin" in roles:
        return f"{model}AdminView"
    return f"{model}View"

result = await toolset.query(
    ctx,
    model="Order",
    view=get_view_for_role("Order", ctx.principal.roles),
    ...
)
```

## Dynamic Views

Create views at runtime:

```python
from ormai.views import view_from_dict

# Define view from dictionary
view_def = {
    "name": "CustomOrderView",
    "fields": {
        "id": {"type": "str"},
        "status": {"type": "str"},
        "total_formatted": {"type": "str", "computed": True},
    },
}

CustomOrderView = view_from_dict(view_def)
```

## View Serialization

Views serialize to JSON Schema for LLM consumption:

```python
schema = UserView.model_json_schema()
```

Output:

```json
{
    "title": "UserView",
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "email": {"type": "string", "description": "User's email (may be masked)"}
    },
    "required": ["id", "name", "email"]
}
```

## Nested Views

Handle relations with nested views:

```python
class OrderItemView(BaseView):
    id: int
    product_name: str
    quantity: int
    price: int

class OrderWithItemsView(BaseView):
    id: int
    status: str
    total: int
    items: list[OrderItemView]  # Nested view
```

### Automatic Nesting

```python
OrderView = factory.create_view(
    "Order",
    include_relations=["items"],
    relation_views={
        "items": "OrderItemView",  # Use specific view for relation
    },
)
```

## View Validation

Views validate data consistency:

```python
from pydantic import ValidationError

try:
    view = OrderView(
        id=123,
        status="invalid_status",  # Not in allowed values
        total=-100,  # Negative not allowed
    )
except ValidationError as e:
    print(e.errors())
```

### Custom Validators

```python
from pydantic import validator

class OrderView(BaseView):
    id: int
    status: str
    total: int

    @validator("status")
    def validate_status(cls, v):
        allowed = ["pending", "confirmed", "shipped", "delivered"]
        if v not in allowed:
            raise ValueError(f"Status must be one of {allowed}")
        return v

    @validator("total")
    def validate_total(cls, v):
        if v < 0:
            raise ValueError("Total cannot be negative")
        return v
```

## Code Generation

Generate view code for your project:

```python
from ormai.codegen import ViewCodeGenerator

generator = ViewCodeGenerator(
    schema=schema,
    policy=policy,
    output_dir="./generated/views",
)

# Generate all views
generator.generate_all()

# Generates:
# ./generated/views/user_views.py
# ./generated/views/order_views.py
# ...
```

Generated code:

```python
# ./generated/views/user_views.py
from ormai.views import BaseView
from pydantic import Field

class UserView(BaseView):
    """Auto-generated view for User model."""

    id: str
    name: str
    email: str = Field(..., description="Masked field")

    class Config:
        orm_model = "User"
```

## Next Steps

- [Code Generation](../guides/code-generation.md) - Generate views and tools
- [API Reference](../api-reference/core.md) - View API details
- [Policies](policies.md) - Policy-view alignment
