# Code Generation Guide

OrmAI includes code generation utilities to create type-safe views, domain tools, and other artifacts from your schema and policy.

## Overview

Code generation helps you:

- Create Pydantic view models aligned with policies
- Generate domain tool stubs
- Maintain type safety across your codebase
- Reduce boilerplate

## View Generation

### Basic Usage

```python
from ormai.codegen import ViewCodeGenerator

generator = ViewCodeGenerator(
    schema=adapter.introspect(),
    policy=policy,
    output_dir="./generated/views",
)

# Generate all views
generator.generate_all()
```

### Output Structure

```
./generated/views/
├── __init__.py
├── user_views.py
├── order_views.py
└── product_views.py
```

### Generated Code

```python
# ./generated/views/user_views.py
"""Auto-generated views for User model."""

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List

class UserView(BaseModel):
    """View for User model aligned with policy."""

    id: str
    name: str
    email: str = Field(..., description="Masked field")
    created_at: datetime

    class Config:
        orm_mode = True

class UserListView(BaseModel):
    """Minimal view for User listings."""

    id: str
    name: str

    class Config:
        orm_mode = True
```

### Customization Options

```python
generator = ViewCodeGenerator(
    schema=schema,
    policy=policy,
    output_dir="./generated/views",

    # Options
    generate_list_views=True,      # Create minimal list views
    generate_detail_views=True,    # Create full detail views
    include_relations=True,        # Include relation views
    max_relation_depth=2,          # Limit nesting
    base_class="BaseModel",        # Pydantic base class
    add_docstrings=True,           # Include docstrings
)
```

### Selective Generation

```python
# Generate for specific models
generator.generate(["User", "Order"])

# Skip certain models
generator.generate_all(exclude=["AuditLog", "InternalConfig"])
```

## Domain Tool Generation

### Basic Usage

```python
from ormai.codegen import DomainToolGenerator

generator = DomainToolGenerator(
    schema=adapter.introspect(),
    policy=policy,
    output_dir="./generated/tools",
)

generator.generate_all()
```

### Output Structure

```
./generated/tools/
├── __init__.py
├── user_tools.py
├── order_tools.py
└── base.py
```

### Generated Stubs

```python
# ./generated/tools/order_tools.py
"""Auto-generated domain tools for Order model."""

from ormai.tools import Tool, ToolResult
from ormai.core import RunContext

class CreateOrderTool(Tool):
    """Create a new Order."""

    name = "create_order"
    description = "Create a new Order record"

    async def execute(
        self,
        ctx: RunContext,
        status: str,
        total: int,
        user_id: str,
    ) -> ToolResult:
        # TODO: Implement business logic

        # Example implementation:
        # return await self.toolset.create(
        #     ctx,
        #     model="Order",
        #     data={
        #         "status": status,
        #         "total": total,
        #         "user_id": user_id,
        #     },
        # )

        raise NotImplementedError("Implement create_order logic")


class UpdateOrderStatusTool(Tool):
    """Update the status of an Order."""

    name = "update_order_status"
    description = "Update the status of an existing Order"

    async def execute(
        self,
        ctx: RunContext,
        order_id: int,
        new_status: str,
    ) -> ToolResult:
        # TODO: Implement business logic
        raise NotImplementedError("Implement update_order_status logic")
```

### Tool Templates

Define custom templates:

```python
generator = DomainToolGenerator(
    schema=schema,
    policy=policy,
    output_dir="./generated/tools",
    templates={
        "create": "custom_create_template.py.jinja2",
        "update": "custom_update_template.py.jinja2",
    },
)
```

## Full Code Generator

Generate everything at once:

```python
from ormai.codegen import CodeGenerator

generator = CodeGenerator(
    schema=adapter.introspect(),
    policy=policy,
    output_dir="./generated",
)

generator.generate_all()
```

### Output Structure

```
./generated/
├── __init__.py
├── views/
│   ├── __init__.py
│   ├── user_views.py
│   └── order_views.py
├── tools/
│   ├── __init__.py
│   ├── user_tools.py
│   └── order_tools.py
├── schemas/
│   ├── __init__.py
│   └── openapi.json
└── types/
    ├── __init__.py
    └── enums.py
```

## CLI Usage

Generate from command line:

```bash
# Generate all
python -m ormai.codegen generate \
    --config ./ormai.yaml \
    --output ./generated

# Generate views only
python -m ormai.codegen generate-views \
    --config ./ormai.yaml \
    --output ./generated/views

# Generate tools only
python -m ormai.codegen generate-tools \
    --config ./ormai.yaml \
    --output ./generated/tools
```

### Configuration File

```yaml
# ormai.yaml
adapter:
  type: sqlalchemy
  connection_string: ${DATABASE_URL}
  base_module: myapp.models

policy:
  path: ./policy.yaml

codegen:
  output_dir: ./generated

  views:
    enabled: true
    list_views: true
    detail_views: true
    max_relation_depth: 2

  tools:
    enabled: true
    include_create: true
    include_update: true
    include_domain: true

  schemas:
    enabled: true
    format: openapi
```

## Regeneration

### Preserving Custom Code

Generated files include markers:

```python
# ./generated/tools/order_tools.py
"""Auto-generated domain tools for Order model.

WARNING: This file is auto-generated. Do not edit directly.
Custom logic should be added in the designated sections.
"""

class CreateOrderTool(Tool):
    # ... generated code ...

    async def execute(self, ctx, **kwargs):
        # === BEGIN CUSTOM CODE ===
        # Your custom logic here (preserved on regeneration)
        # === END CUSTOM CODE ===
        pass
```

### Force Regeneration

```python
generator.generate_all(force=True)  # Overwrites all files
```

### Incremental Updates

```python
generator.generate_all(
    incremental=True,  # Only update changed models
    backup=True,       # Create backups before updating
)
```

## Type Generation

### Enums

```python
# ./generated/types/enums.py
from enum import Enum

class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class PaymentStatus(str, Enum):
    UNPAID = "unpaid"
    PAID = "paid"
    REFUNDED = "refunded"
```

### TypedDicts

```python
# ./generated/types/dicts.py
from typing import TypedDict, Optional

class OrderDict(TypedDict):
    id: int
    status: str
    total: int
    user_id: str
    created_at: str
    updated_at: Optional[str]
```

## OpenAPI Schema Generation

```python
from ormai.codegen import OpenAPIGenerator

generator = OpenAPIGenerator(
    schema=schema,
    policy=policy,
    toolset=toolset,
)

openapi_spec = generator.generate()

# Save to file
with open("./openapi.json", "w") as f:
    json.dump(openapi_spec, f, indent=2)
```

### Generated Spec

```json
{
  "openapi": "3.0.3",
  "info": {
    "title": "OrmAI API",
    "version": "1.0.0"
  },
  "paths": {
    "/query": {
      "post": {
        "operationId": "query",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {"$ref": "#/components/schemas/QueryRequest"}
            }
          }
        }
      }
    }
  },
  "components": {
    "schemas": {
      "OrderView": {
        "type": "object",
        "properties": {
          "id": {"type": "integer"},
          "status": {"type": "string", "enum": ["pending", "confirmed", "shipped"]}
        }
      }
    }
  }
}
```

## Integration with Build

### Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: ormai-codegen
        name: OrmAI Code Generation
        entry: python -m ormai.codegen generate --config ./ormai.yaml
        language: python
        pass_filenames: false
```

### CI/CD

```yaml
# .github/workflows/codegen.yml
name: Code Generation
on: [push]

jobs:
  codegen:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - run: pip install ormai

      - name: Generate code
        run: python -m ormai.codegen generate --config ./ormai.yaml

      - name: Check for changes
        run: |
          if [[ -n $(git status --porcelain generated/) ]]; then
            echo "Generated code is out of date!"
            exit 1
          fi
```

## Best Practices

1. **Version control generated code** - Include in git for transparency

2. **Don't edit generated files directly** - Use custom code sections

3. **Regenerate on schema changes** - Keep views aligned with models

4. **Use incremental mode** - Faster regeneration

5. **Review generated code** - Ensure it meets your standards

6. **Customize templates** - Match your coding style

## Next Steps

- [Views](../concepts/views.md) - Using generated views
- [Custom Tools](custom-tools.md) - Implementing tool stubs
- [Evaluation](evaluation.md) - Testing generated code
