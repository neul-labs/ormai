# Contributing to Ormai

Thank you for your interest in contributing to Ormai! This document provides guidelines and information for contributors.

## Development Setup

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager

### Getting Started

```bash
# Clone the repository
git clone https://github.com/neul-labs/ormai.git
cd ormai

# Install dependencies
uv sync --dev

# Run tests to verify setup
uv run pytest tests/ -v
```

## Development Workflow

### Code Style

We use the following tools for code quality:

- **ruff** - Linting and formatting
- **mypy** - Type checking
- **pytest** - Testing

```bash
# Run linting
uv run ruff check src/ tests/

# Auto-fix lint issues
uv run ruff check src/ tests/ --fix

# Format code
uv run ruff format src/ tests/

# Type checking
uv run mypy src/ormai --ignore-missing-imports

# Run tests
uv run pytest tests/ -v

# Run tests with coverage
uv run pytest tests/ --cov=src/ormai --cov-report=html
```

### Pre-commit Hooks

We recommend setting up pre-commit hooks:

```bash
uv run pre-commit install
```

## Making Changes

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 2. Make Your Changes

- Follow the existing code style
- Add type hints to all functions
- Write docstrings for public APIs
- Add tests for new functionality

### 3. Test Your Changes

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_your_module.py -v

# Run with coverage
uv run pytest tests/ --cov=src/ormai
```

### 4. Submit a Pull Request

- Ensure all tests pass
- Ensure linting passes
- Write a clear PR description
- Reference any related issues

## Project Structure

```
ormai/
├── src/ormai/             # Main source code
│   ├── adapters/          # ORM adapters (sqlalchemy, tortoise, peewee)
│   ├── capability/        # Capability-based access control
│   ├── cli/               # CLI commands
│   ├── protocols/         # MCP, A2A protocols
│   └── ...                # Core modules
├── tests/                 # Test suite
│   ├── unit/              # Unit tests
│   ├── integration/       # Integration tests
│   └── fuzzing/           # Fuzzing/property-based tests
├── examples/              # Example applications
├── docs/                  # Documentation
└── ormai-ts/              # TypeScript package
```

## Adding New Features

### Adding a New ORM Adapter

1. Create `src/ormai/adapters/your_adapter.py`
2. Implement the `BaseAdapter` interface
3. Add to `src/ormai/adapters/__init__.py`
4. Add tests in `tests/unit/test_adapters_your_adapter.py`
5. Add optional dependency in `pyproject.toml`

### Adding a New Integration

1. Create `src/ormai/integrations/your_integration.py`
2. Implement the hook or provider interface
3. Add to `src/ormai/integrations/__init__.py`
4. Add tests and documentation

### Adding CLI Commands

1. Edit `src/ormai/cli/main.py`
2. Add command with `@app.command()` decorator
3. Update documentation

## Testing Guidelines

### Test Structure

- Place tests in `tests/` directory
- Name test files `test_<module>.py`
- Use descriptive test function names

### Test Categories

- **Unit tests** - Test individual functions/classes
- **Integration tests** - Test component interactions
- **Fuzzing tests** - Property-based testing (in `tests/fuzzing/`)

### Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run unit tests only
uv run pytest tests/unit/ -v

# Run with coverage
uv run pytest tests/ --cov=src/ormai

# Run type checking
uv run mypy src/ormai
```

## Documentation

- Use Markdown for documentation
- Place docs in the `docs/` directory
- Include code examples where appropriate

## Code Review Process

1. All changes require a pull request
2. PRs need at least one approval
3. CI checks must pass
4. Maintain test coverage

## Reporting Issues

When reporting issues, please include:

- Python version
- Ormai version
- Minimal reproduction steps
- Error messages/stack traces
- Expected vs actual behavior

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Questions?

- Open a GitHub issue for questions
- Check existing documentation in `docs/`
- Review existing examples in `examples/`

Thank you for contributing to Ormai!
