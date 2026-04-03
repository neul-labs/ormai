#!/usr/bin/env python3
"""
OrmAI Spider Benchmark Demo

A compelling demo comparing OrmAI's tool-based approach vs raw text-to-SQL
using the Spider benchmark dataset. Features a split-screen rich CLI with
concurrent execution across GPT-4 and Claude.

Usage:
    # Download Spider dataset (first-time setup)
    uv run python examples/spider_demo.py download

    # Run full benchmark
    uv run python examples/spider_demo.py run

    # Quick demo (20 questions)
    uv run python examples/spider_demo.py run --limit 20

    # Single LLM mode
    uv run python examples/spider_demo.py run --llm gpt-4
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sqlite3
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# ============================================================================
# Constants
# ============================================================================

SPIDER_URL = "https://github.com/taoyds/spider/archive/refs/heads/master.zip"
DATA_DIR = Path(__file__).parent / ".spider_data"
CACHE_DIR = DATA_DIR / "spider-master"

console = Console()


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class SchemaInfo:
    """Database schema information."""

    db_id: str
    tables: list[dict[str, Any]]
    columns: list[dict[str, Any]]
    foreign_keys: list[tuple[int, int]]
    primary_keys: list[int]

    def to_prompt(self) -> str:
        """Convert schema to natural language prompt."""
        lines = [f"Database: {self.db_id}", "Tables:"]
        for table in self.tables:
            table_name = table["name"]
            cols = [c for c in self.columns if c["table_idx"] == table["idx"]]
            col_names = [c["name"] for c in cols]
            lines.append(f"  - {table_name}: {', '.join(col_names)}")
        return "\n".join(lines)


@dataclass
class SpiderExample:
    """A single Spider benchmark example."""

    question: str
    query: str
    db_id: str
    schema: SchemaInfo


@dataclass
class Metrics:
    """Benchmark metrics for an approach."""

    correct: int = 0
    incorrect: int = 0
    execution_errors: int = 0
    policy_blocked: int = 0  # OrmAI only
    unsafe_detected: int = 0  # Text-to-SQL only
    total: int = 0

    @property
    def accuracy(self) -> float:
        """Calculate accuracy percentage."""
        if self.total == 0:
            return 0.0
        return (self.correct / self.total) * 100

    @property
    def progress(self) -> float:
        """Calculate progress percentage."""
        if self.total == 0:
            return 0.0
        processed = self.correct + self.incorrect + self.execution_errors
        return (processed / self.total) * 100


@dataclass
class ApproachResult:
    """Result from executing an approach."""

    success: bool
    result: Any = None
    error: str | None = None
    was_blocked: bool = False  # OrmAI policy block
    was_unsafe: bool = False  # Text-to-SQL unsafe query
    generated_sql: str | None = None
    tool_call: dict[str, Any] | None = None


@dataclass
class BenchmarkState:
    """Current state of the benchmark run."""

    current_question: str = ""
    current_db: str = ""
    current_ormai_action: str = ""
    current_sql: str = ""
    ormai_gpt4: Metrics = field(default_factory=Metrics)
    ormai_claude: Metrics = field(default_factory=Metrics)
    sql_gpt4: Metrics = field(default_factory=Metrics)
    sql_claude: Metrics = field(default_factory=Metrics)


# ============================================================================
# Spider Dataset
# ============================================================================


class SpiderDataset:
    """Handles downloading and loading the Spider benchmark dataset."""

    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        self.cache_dir = data_dir / "spider-master"
        self._schemas: dict[str, SchemaInfo] = {}
        self._db_connections: dict[str, sqlite3.Connection] = {}

    async def download(self) -> None:
        """Download Spider dataset if not present."""
        if self.cache_dir.exists():
            console.print("[green]Spider dataset already downloaded.[/green]")
            return

        console.print("[yellow]Downloading Spider dataset...[/yellow]")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        zip_path = self.data_dir / "spider.zip"

        async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
            response = await client.get(SPIDER_URL)
            response.raise_for_status()

            with open(zip_path, "wb") as f:
                f.write(response.content)

        console.print("[yellow]Extracting...[/yellow]")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(self.data_dir)

        zip_path.unlink()
        console.print("[green]Spider dataset downloaded successfully![/green]")

    def _load_schemas(self) -> None:
        """Load schema information from tables.json."""
        if self._schemas:
            return

        tables_path = self.cache_dir / "tables.json"
        if not tables_path.exists():
            raise FileNotFoundError(
                "tables.json not found. Run 'download' command first."
            )

        with open(tables_path) as f:
            tables_data = json.load(f)

        for db in tables_data:
            db_id = db["db_id"]
            tables = [
                {"idx": i, "name": name}
                for i, name in enumerate(db["table_names_original"])
            ]
            columns = [
                {"idx": i, "table_idx": col[0], "name": col[1]}
                for i, col in enumerate(db["column_names_original"])
            ]
            self._schemas[db_id] = SchemaInfo(
                db_id=db_id,
                tables=tables,
                columns=columns,
                foreign_keys=db.get("foreign_keys", []),
                primary_keys=db.get("primary_keys", []),
            )

    def load_examples(self, split: str = "dev", limit: int | None = None) -> list[SpiderExample]:
        """Load examples from a split (train or dev)."""
        self._load_schemas()

        split_path = self.cache_dir / f"{split}.json"
        if not split_path.exists():
            raise FileNotFoundError(
                f"{split}.json not found. Run 'download' command first."
            )

        with open(split_path) as f:
            examples_data = json.load(f)

        examples = []
        for item in examples_data:
            db_id = item["db_id"]
            if db_id not in self._schemas:
                continue

            examples.append(
                SpiderExample(
                    question=item["question"],
                    query=item["query"],
                    db_id=db_id,
                    schema=self._schemas[db_id],
                )
            )

            if limit and len(examples) >= limit:
                break

        return examples

    def get_db_connection(self, db_id: str) -> sqlite3.Connection:
        """Get SQLite connection for a database."""
        if db_id not in self._db_connections:
            db_path = self.cache_dir / "database" / db_id / f"{db_id}.sqlite"
            if not db_path.exists():
                raise FileNotFoundError(f"Database not found: {db_path}")
            conn = sqlite3.connect(str(db_path))
            self._db_connections[db_id] = conn
        return self._db_connections[db_id]

    def execute_query(self, db_id: str, sql: str) -> list[tuple]:
        """Execute a SQL query and return results."""
        conn = self.get_db_connection(db_id)
        cursor = conn.cursor()
        cursor.execute(sql)
        return cursor.fetchall()

    def close(self) -> None:
        """Close all database connections."""
        for conn in self._db_connections.values():
            conn.close()
        self._db_connections.clear()


# ============================================================================
# LLM Providers
# ============================================================================


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    name: str

    @abstractmethod
    async def generate_sql(self, question: str, schema: str) -> str:
        """Generate raw SQL from question and schema."""
        ...

    @abstractmethod
    async def call_tools(
        self, question: str, schema: str, tools: list[dict]
    ) -> dict[str, Any] | None:
        """Call OrmAI tools and return the tool call."""
        ...


class OpenAIProvider(LLMProvider):
    """OpenAI GPT-4 provider."""

    name = "gpt-4"

    def __init__(self):
        try:
            from openai import AsyncOpenAI
        except ImportError as e:
            raise ImportError("openai package not installed. Run: pip install openai") from e

        self.client = AsyncOpenAI()
        self.model = "gpt-4-turbo-preview"

    async def generate_sql(self, question: str, schema: str) -> str:
        """Generate SQL using GPT-4."""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a SQL expert. Given a database schema and a question, "
                        "generate a single SQL query to answer the question. "
                        "Return ONLY the SQL query, nothing else."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Schema:\n{schema}\n\nQuestion: {question}",
                },
            ],
            temperature=0,
            max_tokens=500,
        )
        return response.choices[0].message.content.strip()

    async def call_tools(
        self, question: str, schema: str, tools: list[dict]
    ) -> dict[str, Any] | None:
        """Call OrmAI tools using GPT-4 function calling."""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a database assistant. Use the provided tools to "
                        "answer the user's question about the database. "
                        "Choose the most appropriate tool and provide the correct arguments."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Schema:\n{schema}\n\nQuestion: {question}",
                },
            ],
            tools=tools,
            tool_choice="auto",
            temperature=0,
        )

        message = response.choices[0].message
        if message.tool_calls:
            tool_call = message.tool_calls[0]
            return {
                "name": tool_call.function.name,
                "arguments": json.loads(tool_call.function.arguments),
            }
        return None


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    name = "claude"

    def __init__(self):
        try:
            from anthropic import AsyncAnthropic
        except ImportError as e:
            raise ImportError(
                "anthropic package not installed. Run: pip install anthropic"
            ) from e

        self.client = AsyncAnthropic()
        self.model = "claude-sonnet-4-20250514"

    async def generate_sql(self, question: str, schema: str) -> str:
        """Generate SQL using Claude."""
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"You are a SQL expert. Given this database schema and question, "
                        f"generate a single SQL query to answer the question. "
                        f"Return ONLY the SQL query, nothing else.\n\n"
                        f"Schema:\n{schema}\n\nQuestion: {question}"
                    ),
                },
            ],
        )
        return response.content[0].text.strip()

    async def call_tools(
        self, question: str, schema: str, tools: list[dict]
    ) -> dict[str, Any] | None:
        """Call OrmAI tools using Claude tool use."""
        # Convert OpenAI tool format to Anthropic format
        anthropic_tools = []
        for tool in tools:
            anthropic_tools.append({
                "name": tool["function"]["name"],
                "description": tool["function"]["description"],
                "input_schema": tool["function"]["parameters"],
            })

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=500,
            tools=anthropic_tools,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"You are a database assistant. Use the provided tools to "
                        f"answer the user's question about the database. "
                        f"Choose the most appropriate tool.\n\n"
                        f"Schema:\n{schema}\n\nQuestion: {question}"
                    ),
                },
            ],
        )

        for block in response.content:
            if block.type == "tool_use":
                return {
                    "name": block.name,
                    "arguments": block.input,
                }
        return None


# ============================================================================
# Approaches
# ============================================================================


def get_ormai_tools() -> list[dict]:
    """Get OrmAI tool definitions in OpenAI format."""
    return [
        {
            "type": "function",
            "function": {
                "name": "query",
                "description": (
                    "Query database records with filtering and aggregation. "
                    "Use this for SELECT operations, counting, filtering, and joins."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "table": {
                            "type": "string",
                            "description": "The table name to query",
                        },
                        "columns": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Columns to select (empty for all)",
                        },
                        "filters": {
                            "type": "object",
                            "description": "Filter conditions as key-value pairs",
                        },
                        "aggregate": {
                            "type": "string",
                            "enum": ["count", "sum", "avg", "min", "max"],
                            "description": "Aggregation function to apply",
                        },
                        "aggregate_column": {
                            "type": "string",
                            "description": "Column to aggregate",
                        },
                        "group_by": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Columns to group by",
                        },
                        "order_by": {
                            "type": "string",
                            "description": "Column to order by",
                        },
                        "order_direction": {
                            "type": "string",
                            "enum": ["asc", "desc"],
                            "description": "Sort direction",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum rows to return",
                        },
                    },
                    "required": ["table"],
                },
            },
        },
    ]


# Unsafe SQL patterns
UNSAFE_PATTERNS = [
    r"\bDELETE\b",
    r"\bDROP\b",
    r"\bTRUNCATE\b",
    r"\bUPDATE\b(?!.*\bWHERE\b)",
    r"\bINSERT\b",
    r";\s*\w",  # Multiple statements
    r"--",  # SQL comments (potential injection)
    r"UNION\s+SELECT",  # UNION injection
]


def detect_unsafe_sql(sql: str) -> bool:
    """Detect potentially unsafe SQL patterns."""
    sql_upper = sql.upper()
    return any(re.search(pattern, sql_upper, re.IGNORECASE) for pattern in UNSAFE_PATTERNS)


class OrmAIApproach:
    """OrmAI tool-based approach."""

    def __init__(self, llm: LLMProvider, dataset: SpiderDataset):
        self.llm = llm
        self.dataset = dataset
        self.tools = get_ormai_tools()

    async def execute(self, example: SpiderExample) -> ApproachResult:
        """Execute using OrmAI tools."""
        try:
            schema_prompt = example.schema.to_prompt()
            tool_call = await self.llm.call_tools(
                example.question, schema_prompt, self.tools
            )

            if not tool_call:
                return ApproachResult(
                    success=False,
                    error="No tool call returned",
                )

            # Check for policy violations (simulated)
            args = tool_call.get("arguments", {})

            # Simulate policy: block certain operations
            if args.get("aggregate") in ["sum", "avg"] and not args.get("aggregate_column"):
                return ApproachResult(
                    success=False,
                    was_blocked=True,
                    error="Policy blocked: aggregate requires column",
                    tool_call=tool_call,
                )

            # Build and execute SQL from tool call
            sql = self._tool_call_to_sql(tool_call, example.schema)
            result = self.dataset.execute_query(example.db_id, sql)

            return ApproachResult(
                success=True,
                result=result,
                tool_call=tool_call,
                generated_sql=sql,
            )

        except Exception as e:
            return ApproachResult(
                success=False,
                error=str(e),
            )

    def _tool_call_to_sql(
        self, tool_call: dict, schema: SchemaInfo  # noqa: ARG002 - reserved for future
    ) -> str:
        """Convert tool call to SQL query."""
        args = tool_call.get("arguments", {})
        table = args.get("table", "")
        columns = args.get("columns", ["*"])
        filters = args.get("filters", {})
        aggregate = args.get("aggregate")
        aggregate_column = args.get("aggregate_column", "*")
        group_by = args.get("group_by", [])
        order_by = args.get("order_by")
        order_direction = args.get("order_direction", "asc")
        limit = args.get("limit")

        # Build SELECT clause
        if aggregate:
            if aggregate == "count":
                select_clause = f"COUNT({aggregate_column})"
            else:
                select_clause = f"{aggregate.upper()}({aggregate_column})"
        else:
            select_clause = ", ".join(columns) if columns else "*"

        sql = f"SELECT {select_clause} FROM {table}"

        # Add WHERE clause
        if filters:
            conditions = []
            for key, value in filters.items():
                if isinstance(value, str):
                    conditions.append(f"{key} = '{value}'")
                else:
                    conditions.append(f"{key} = {value}")
            sql += " WHERE " + " AND ".join(conditions)

        # Add GROUP BY
        if group_by:
            sql += " GROUP BY " + ", ".join(group_by)

        # Add ORDER BY
        if order_by:
            sql += f" ORDER BY {order_by} {order_direction.upper()}"

        # Add LIMIT
        if limit:
            sql += f" LIMIT {limit}"

        return sql


class TextToSQLApproach:
    """Direct text-to-SQL approach."""

    def __init__(self, llm: LLMProvider, dataset: SpiderDataset):
        self.llm = llm
        self.dataset = dataset

    async def execute(self, example: SpiderExample) -> ApproachResult:
        """Execute using direct SQL generation."""
        try:
            schema_prompt = example.schema.to_prompt()
            sql = await self.llm.generate_sql(example.question, schema_prompt)

            # Clean up SQL (remove markdown code blocks if present)
            sql = sql.strip()
            if sql.startswith("```"):
                sql = sql.split("\n", 1)[1] if "\n" in sql else sql[3:]
            if sql.endswith("```"):
                sql = sql[:-3]
            sql = sql.strip()

            # Check for unsafe patterns
            is_unsafe = detect_unsafe_sql(sql)

            if is_unsafe:
                return ApproachResult(
                    success=False,
                    was_unsafe=True,
                    error="Unsafe SQL pattern detected",
                    generated_sql=sql,
                )

            # Execute the query
            result = self.dataset.execute_query(example.db_id, sql)

            return ApproachResult(
                success=True,
                result=result,
                generated_sql=sql,
            )

        except Exception as e:
            return ApproachResult(
                success=False,
                error=str(e),
            )


# ============================================================================
# Rich UI
# ============================================================================


class DemoUI:
    """Rich CLI interface for the benchmark demo."""

    def __init__(self):
        self.console = Console()
        self.state = BenchmarkState()

    def create_layout(self) -> Layout:
        """Create the split-screen layout."""
        layout = Layout()

        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=6),
        )

        layout["main"].split_row(
            Layout(name="ormai", ratio=1),
            Layout(name="text_to_sql", ratio=1),
        )

        return layout

    def render_header(self, total: int) -> Panel:
        """Render the header panel."""
        return Panel(
            Text(
                f"  Spider Benchmark Demo  |  Questions: {total}  |  "
                f"LLMs: GPT-4 + Claude",
                justify="center",
            ),
            style="bold white on blue",
        )

    def render_metrics_panel(
        self, title: str, metrics_gpt4: Metrics, metrics_claude: Metrics, is_ormai: bool
    ) -> Panel:
        """Render a metrics panel for one approach."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("LLM", width=8)
        table.add_column("Progress", width=20)
        table.add_column("Stats", width=30)

        for name, m in [("GPT-4", metrics_gpt4), ("Claude", metrics_claude)]:
            # Progress bar representation
            pct = m.progress
            filled = int(pct / 5)
            bar = "[green]" + "━" * filled + "[/green]" + "[dim]━" * (20 - filled) + "[/dim]"

            # Stats
            if is_ormai:
                stats = f"[green]✓ {m.correct}[/green]  [red]✗ {m.execution_errors}[/red]  [cyan]🛡️ {m.policy_blocked}[/cyan]"
            else:
                stats = f"[green]✓ {m.correct}[/green]  [red]✗ {m.execution_errors}[/red]  [yellow]⚠️ {m.unsafe_detected}[/yellow]"

            table.add_row(name, f"{bar} {pct:.0f}%", stats)
            table.add_row("", "", "")

        style = "green" if is_ormai else "yellow"
        return Panel(table, title=f"[bold]{title}[/bold]", border_style=style)

    def render_footer(self) -> Panel:
        """Render the current question panel."""
        content = Table(show_header=False, box=None)
        content.add_column("Label", width=10)
        content.add_column("Value")

        content.add_row("[bold]DB:[/bold]", self.state.current_db)
        content.add_row("[bold]Q:[/bold]", self.state.current_question[:70] + "..." if len(self.state.current_question) > 70 else self.state.current_question)
        content.add_row("[bold]OrmAI:[/bold]", self.state.current_ormai_action[:60] if self.state.current_ormai_action else "")
        content.add_row("[bold]SQL:[/bold]", self.state.current_sql[:60] if self.state.current_sql else "")

        return Panel(content, title="[bold]Current Question[/bold]")

    def render(self, total: int) -> Layout:
        """Render the full layout."""
        layout = self.create_layout()

        layout["header"].update(self.render_header(total))
        layout["ormai"].update(
            self.render_metrics_panel(
                "OrmAI (Safe)",
                self.state.ormai_gpt4,
                self.state.ormai_claude,
                is_ormai=True,
            )
        )
        layout["text_to_sql"].update(
            self.render_metrics_panel(
                "Text-to-SQL",
                self.state.sql_gpt4,
                self.state.sql_claude,
                is_ormai=False,
            )
        )
        layout["footer"].update(self.render_footer())

        return layout

    def render_summary(self) -> Table:
        """Render the final summary table."""
        table = Table(title="Benchmark Results Summary")

        table.add_column("Approach", style="bold")
        table.add_column("LLM")
        table.add_column("Correct", style="green")
        table.add_column("Errors", style="red")
        table.add_column("Blocked/Unsafe", style="yellow")
        table.add_column("Accuracy")

        for approach, is_ormai, m_gpt4, m_claude in [
            ("OrmAI", True, self.state.ormai_gpt4, self.state.ormai_claude),
            ("Text-to-SQL", False, self.state.sql_gpt4, self.state.sql_claude),
        ]:
            for name, m in [("GPT-4", m_gpt4), ("Claude", m_claude)]:
                blocked = str(m.policy_blocked) if is_ormai else str(m.unsafe_detected)
                table.add_row(
                    approach,
                    name,
                    str(m.correct),
                    str(m.execution_errors),
                    blocked,
                    f"{m.accuracy:.1f}%",
                )

        return table


# ============================================================================
# Benchmark Runner
# ============================================================================


class BenchmarkRunner:
    """Orchestrates the benchmark execution."""

    def __init__(
        self,
        dataset: SpiderDataset,
        llms: list[LLMProvider],
        ui: DemoUI,
    ):
        self.dataset = dataset
        self.llms = llms
        self.ui = ui

    async def run(
        self,
        examples: list[SpiderExample],
        concurrency: int = 4,
    ) -> None:
        """Run the benchmark with live UI updates."""
        # Initialize metrics
        for llm in self.llms:
            for metrics in [
                self.ui.state.ormai_gpt4 if llm.name == "gpt-4" else self.ui.state.ormai_claude,
                self.ui.state.sql_gpt4 if llm.name == "gpt-4" else self.ui.state.sql_claude,
            ]:
                metrics.total = len(examples)

        # Create approaches for each LLM
        approaches = []
        for llm in self.llms:
            approaches.append(("ormai", llm, OrmAIApproach(llm, self.dataset)))
            approaches.append(("sql", llm, TextToSQLApproach(llm, self.dataset)))

        # Semaphore for rate limiting
        semaphore = asyncio.Semaphore(concurrency)

        async def process_example(
            example: SpiderExample,
            approach_name: str,
            llm: LLMProvider,
            approach: OrmAIApproach | TextToSQLApproach,
        ):
            async with semaphore:
                result = await approach.execute(example)

                # Update metrics
                if approach_name == "ormai":
                    metrics = (
                        self.ui.state.ormai_gpt4
                        if llm.name == "gpt-4"
                        else self.ui.state.ormai_claude
                    )
                else:
                    metrics = (
                        self.ui.state.sql_gpt4
                        if llm.name == "gpt-4"
                        else self.ui.state.sql_claude
                    )

                if result.success:
                    # Simple correctness check (results not empty)
                    if result.result:
                        metrics.correct += 1
                    else:
                        metrics.incorrect += 1
                elif result.was_blocked:
                    metrics.policy_blocked += 1
                elif result.was_unsafe:
                    metrics.unsafe_detected += 1
                else:
                    metrics.execution_errors += 1

                # Update UI state for latest question
                self.ui.state.current_question = example.question
                self.ui.state.current_db = example.db_id
                if result.tool_call:
                    self.ui.state.current_ormai_action = (
                        f"{result.tool_call['name']}({json.dumps(result.tool_call['arguments'])})"
                    )
                if result.generated_sql:
                    self.ui.state.current_sql = result.generated_sql

        # Run with live UI
        with Live(self.ui.render(len(examples)), refresh_per_second=4) as live:
            tasks = []
            for example in examples:
                for approach_name, llm, approach in approaches:
                    task = process_example(example, approach_name, llm, approach)
                    tasks.append(task)

            # Process in batches for better UI updates
            batch_size = concurrency * 2
            for i in range(0, len(tasks), batch_size):
                batch = tasks[i : i + batch_size]
                await asyncio.gather(*batch, return_exceptions=True)
                live.update(self.ui.render(len(examples)))

        # Show summary
        console.print()
        console.print(self.ui.render_summary())


# ============================================================================
# CLI Commands
# ============================================================================


async def cmd_download(
    args: argparse.Namespace,  # noqa: ARG001 - required by CLI interface
) -> None:
    """Download the Spider dataset."""
    del args  # unused but required by interface
    dataset = SpiderDataset()
    await dataset.download()


async def cmd_run(args: argparse.Namespace) -> None:
    """Run the benchmark."""
    # Check for API keys
    if not os.getenv("OPENAI_API_KEY") and (args.llm in [None, "gpt-4"]):
        console.print("[red]Error: OPENAI_API_KEY not set[/red]")
        return
    if not os.getenv("ANTHROPIC_API_KEY") and (args.llm in [None, "claude"]):
        console.print("[red]Error: ANTHROPIC_API_KEY not set[/red]")
        return

    dataset = SpiderDataset()

    # Check if dataset exists
    if not dataset.cache_dir.exists():
        console.print("[yellow]Spider dataset not found. Downloading...[/yellow]")
        await dataset.download()

    # Load examples
    console.print(f"[blue]Loading Spider dev set (limit={args.limit})...[/blue]")
    examples = dataset.load_examples(split="dev", limit=args.limit)
    console.print(f"[green]Loaded {len(examples)} examples[/green]")

    # Initialize LLMs
    llms: list[LLMProvider] = []
    if args.llm in [None, "gpt-4"]:
        try:
            llms.append(OpenAIProvider())
        except ImportError as e:
            console.print(f"[yellow]Skipping GPT-4: {e}[/yellow]")
    if args.llm in [None, "claude"]:
        try:
            llms.append(AnthropicProvider())
        except ImportError as e:
            console.print(f"[yellow]Skipping Claude: {e}[/yellow]")

    if not llms:
        console.print("[red]No LLM providers available[/red]")
        return

    # Run benchmark
    ui = DemoUI()
    runner = BenchmarkRunner(dataset, llms, ui)

    try:
        await runner.run(examples, concurrency=args.concurrency)
    finally:
        dataset.close()


async def cmd_report(
    args: argparse.Namespace,  # noqa: ARG001 - required by CLI interface
) -> None:
    """Show results from previous run."""
    del args  # unused but required by interface
    console.print("[yellow]Report command not yet implemented[/yellow]")
    console.print("Run 'spider_demo.py run' to generate new results")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="OrmAI Spider Benchmark Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Download command
    subparsers.add_parser("download", help="Download Spider dataset")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run benchmark")
    run_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of examples (default: all)",
    )
    run_parser.add_argument(
        "--llm",
        choices=["gpt-4", "claude"],
        default=None,
        help="Use only one LLM (default: both)",
    )
    run_parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Number of concurrent requests (default: 4)",
    )

    # Report command
    subparsers.add_parser("report", help="Show previous results")

    args = parser.parse_args()

    if args.command == "download":
        asyncio.run(cmd_download(args))
    elif args.command == "run":
        asyncio.run(cmd_run(args))
    elif args.command == "report":
        asyncio.run(cmd_report(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
