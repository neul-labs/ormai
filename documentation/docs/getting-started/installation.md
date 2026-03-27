# Installation

## Requirements

- Python 3.10 or higher
- One of the supported ORMs: SQLAlchemy, Tortoise, Peewee, Django, or SQLModel

## Installing OrmAI

### Basic Installation

```bash
pip install ormai
```

### With ORM-Specific Extras

Install with extras for your preferred ORM:

=== "SQLAlchemy"

    ```bash
    pip install ormai[sqlalchemy]
    ```

=== "Tortoise"

    ```bash
    pip install ormai[tortoise]
    ```

=== "Peewee"

    ```bash
    pip install ormai[peewee]
    ```

=== "Django"

    ```bash
    pip install ormai[django]
    ```

=== "All ORMs"

    ```bash
    pip install ormai[all]
    ```

### Using UV (Recommended)

If you're using [uv](https://github.com/astral-sh/uv) as your package manager:

```bash
uv add ormai
uv add ormai --extra sqlalchemy
```

### Development Installation

For development or contributing:

```bash
git clone https://github.com/ormai/ormai.git
cd ormai
uv sync --all-extras
```

## Optional Dependencies

### MCP Server Support

For Model Context Protocol server integration:

```bash
pip install ormai[mcp]
```

### FastAPI Integration

For FastAPI integration:

```bash
pip install ormai[fastapi]
```

### Full Installation

Install all optional dependencies:

```bash
pip install ormai[all]
```

## Verifying Installation

Verify your installation by importing OrmAI:

```python
import ormai
print(ormai.__version__)
```

Or check the available quickstart functions:

```python
from ormai.quickstart import mount_sqlalchemy, mount_tortoise, mount_peewee
print("OrmAI installed successfully!")
```

## TypeScript Edition

For TypeScript/Node.js projects, see the [TypeScript Edition](../integrations/typescript.md) documentation.

```bash
npm install ormai
# or
yarn add ormai
```
