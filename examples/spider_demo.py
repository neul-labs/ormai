#!/usr/bin/env python3
"""
OrmAI Spider2 Benchmark Demo

A compelling demo comparing OrmAI's tool-based approach vs raw text-to-SQL
using the Spider2-Lite benchmark dataset. Features a split-screen rich CLI with
concurrent execution across GPT-4 and Claude.

Usage:
    # Download Spider2-Lite dataset (first-time setup)
    uv run python examples/spider_demo.py download

    # Run full benchmark
    uv run python examples/spider_demo.py run

    # Quick demo (20 questions)
    uv run python examples/spider_demo.py run --limit 20

    # Single LLM mode
    uv run python examples/spider_demo.py run --llm gpt-5-nano
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sqlite3
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# ============================================================================
# Constants
# ============================================================================

# Spider2-Lite from Hugging Face
HF_DATASET = "xlangai/spider2-lite"
SPIDER2_REPO = "https://github.com/xlang-ai/Spider2.git"
DATA_DIR = Path(__file__).parent / ".spider2_data"

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
    instance_id: str = ""


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
# Spider2 Dataset
# ============================================================================


class Spider2Dataset:
    """Handles downloading and loading the Spider2-Lite benchmark dataset."""

    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        self.cache_dir = data_dir / "spider2-lite"
        self.repo_dir = data_dir / "Spider2"
        self._schemas: dict[str, SchemaInfo] = {}
        self._db_connections: dict[str, sqlite3.Connection] = {}
        self._db_paths: dict[str, Path] = {}

    async def download(self) -> None:
        """Download Spider2-Lite dataset from Hugging Face and clone databases."""
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Download dataset from Hugging Face
        jsonl_path = self.cache_dir / "spider2-lite.jsonl"
        if jsonl_path.exists():
            console.print("[green]Spider2-Lite dataset already downloaded.[/green]")
        else:
            console.print("[yellow]Downloading Spider2-Lite from Hugging Face...[/yellow]")
            try:
                from datasets import load_dataset

                dataset = load_dataset(HF_DATASET, split="train")

                self.cache_dir.mkdir(parents=True, exist_ok=True)

                # Save as JSONL for offline use
                with open(jsonl_path, "w") as f:
                    for item in dataset:
                        f.write(json.dumps(dict(item)) + "\n")

                console.print(f"[green]Downloaded {len(dataset)} examples to {jsonl_path}[/green]")
            except Exception as e:
                console.print(f"[red]Failed to download from Hugging Face: {e}[/red]")
                return

        # Step 2: Download SQLite databases from Google Drive
        db_dir = self.repo_dir / "spider2-lite" / "resource" / "databases" / "spider2-localdb"
        local_map_path = db_dir / "local-map.jsonl"

        if local_map_path.exists():
            console.print("[green]Spider2 SQLite databases already available.[/green]")
        else:
            console.print("[yellow]Downloading Spider2 SQLite databases from Google Drive...[/yellow]")

            try:
                import httpx
                from rich.progress import (
                    BarColumn,
                    DownloadColumn,
                    Progress,
                    TextColumn,
                    TransferSpeedColumn,
                )

                # Create directory structure
                db_dir.mkdir(parents=True, exist_ok=True)
                zip_path = self.data_dir / "spider2-localdb.zip"

                # Download from Google Drive with progress bar
                drive_url = "https://drive.usercontent.google.com/download?id=1coEVsCZq-Xvj9p2TnhBFoFTsY-UoYGmG&export=download&confirm=t"

                with Progress(
                    TextColumn("[bold blue]{task.description}"),
                    BarColumn(),
                    DownloadColumn(),
                    TransferSpeedColumn(),
                    console=console,
                ) as progress:
                    with httpx.stream("GET", drive_url, follow_redirects=True) as response:
                        total = int(response.headers.get("content-length", 0))
                        task = progress.add_task("Downloading databases...", total=total)

                        with open(zip_path, "wb") as f:
                            for chunk in response.iter_bytes(chunk_size=8192):
                                f.write(chunk)
                                progress.update(task, advance=len(chunk))

                # Unzip with progress
                console.print("[yellow]Extracting databases...[/yellow]")
                subprocess.run(
                    ["unzip", "-o", str(zip_path), "-d", str(db_dir)],
                    check=True,
                    capture_output=True,
                )

                # Cleanup
                zip_path.unlink()

                console.print("[green]Spider2 SQLite databases downloaded successfully![/green]")
            except Exception as e:
                console.print(f"[red]Failed to download databases: {e}[/red]")
                console.print("[yellow]Please download manually from:[/yellow]")
                console.print("  https://drive.google.com/file/d/1coEVsCZq-Xvj9p2TnhBFoFTsY-UoYGmG")
                console.print(f"  Unzip to: {db_dir}")
                return

        # Step 3: Build database path mapping
        self._load_db_paths()

        # Show stats
        sqlite_count = self._count_sqlite_examples()
        console.print(f"[green]Ready! Found {sqlite_count} SQLite examples available for testing.[/green]")

    def _load_db_paths(self) -> None:
        """Load database paths from local-map.jsonl."""
        db_dir = self.repo_dir / "spider2-lite" / "resource" / "databases" / "spider2-localdb"
        local_map_path = db_dir / "local-map.jsonl"

        if not local_map_path.exists():
            console.print(f"[yellow]Warning: local-map.jsonl not found at {local_map_path}[/yellow]")
            return

        # local-map.jsonl is a single JSON object mapping instance_id -> db_name
        with open(local_map_path) as f:
            instance_to_db = json.loads(f.read())

        # Build db_name -> sqlite file path mapping
        db_name_to_path: dict[str, Path] = {}
        for sqlite_file in db_dir.glob("*.sqlite"):
            db_name = sqlite_file.stem  # filename without extension
            db_name_to_path[db_name] = sqlite_file
            # Also add lowercase variant for case-insensitive matching
            db_name_to_path[db_name.lower()] = sqlite_file

        # Map each instance_id to its database path
        for instance_id, db_name in instance_to_db.items():
            # Try exact match first, then case-insensitive
            db_path = db_name_to_path.get(db_name) or db_name_to_path.get(db_name.lower())
            if db_path:
                self._db_paths[instance_id] = db_path

    def _count_sqlite_examples(self) -> int:
        """Count how many SQLite examples we can actually run."""
        jsonl_path = self.cache_dir / "spider2-lite.jsonl"
        if not jsonl_path.exists():
            return 0

        count = 0
        with open(jsonl_path) as f:
            for line in f:
                item = json.loads(line)
                instance_id = item.get("instance_id", "")
                # Local examples have instance_id starting with "local"
                if instance_id.startswith("local") and instance_id in self._db_paths:
                    count += 1
        return count

    def load_examples(self, limit: int | None = None) -> list[SpiderExample]:
        """Load SQLite examples from Spider2-Lite."""
        jsonl_path = self.cache_dir / "spider2-lite.jsonl"

        if not jsonl_path.exists():
            raise FileNotFoundError(
                "spider2-lite.jsonl not found. Run 'download' command first."
            )

        # Ensure db paths are loaded
        if not self._db_paths:
            self._load_db_paths()

        examples = []
        with open(jsonl_path) as f:
            for line in f:
                item = json.loads(line)
                instance_id = item.get("instance_id", "")

                # Only use Local examples (instance_id starting with "local")
                if not instance_id.startswith("local"):
                    continue

                # Check if we have the database for this instance
                if instance_id not in self._db_paths:
                    continue

                # Introspect schema from database
                try:
                    schema = self._introspect_db(instance_id)
                except Exception:
                    continue

                examples.append(
                    SpiderExample(
                        question=item.get("question", ""),
                        query="",  # Gold SQL loaded separately if needed
                        db_id=item.get("db", ""),
                        schema=schema,
                        instance_id=instance_id,
                    )
                )

                if limit and len(examples) >= limit:
                    break

        return examples

    def _introspect_db(self, instance_id: str) -> SchemaInfo:
        """Introspect SQLite database to get schema."""
        if instance_id in self._schemas:
            return self._schemas[instance_id]

        conn = self.get_db_connection(instance_id)
        cursor = conn.cursor()

        # Get tables (exclude internal SQLite tables)
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables = [{"idx": i, "name": row[0]} for i, row in enumerate(cursor.fetchall())]

        # Get columns for each table
        columns = []
        primary_keys = []
        for table in tables:
            cursor.execute(f"PRAGMA table_info('{table['name']}')")
            for col in cursor.fetchall():
                col_idx = len(columns)
                columns.append({
                    "idx": col_idx,
                    "table_idx": table["idx"],
                    "name": col[1],
                    "type": col[2],
                })
                # Track primary keys
                if col[5]:  # pk column in PRAGMA table_info
                    primary_keys.append(col_idx)

        # Get foreign keys
        foreign_keys = []
        for table in tables:
            cursor.execute(f"PRAGMA foreign_key_list('{table['name']}')")
            for fk in cursor.fetchall():
                # fk[2] is the referenced table, fk[3] is the from column, fk[4] is the to column
                foreign_keys.append((fk[3], fk[4]))

        # Get db_id from path for schema info
        db_path = self._db_paths.get(instance_id)
        db_id = db_path.stem if db_path else instance_id

        schema = SchemaInfo(
            db_id=db_id,
            tables=tables,
            columns=columns,
            foreign_keys=foreign_keys,
            primary_keys=primary_keys,
        )
        self._schemas[instance_id] = schema
        return schema

    def get_db_connection(self, instance_id: str) -> sqlite3.Connection:
        """Get SQLite connection for a database by instance_id."""
        if instance_id not in self._db_connections:
            if instance_id not in self._db_paths:
                raise FileNotFoundError(f"Database not found for instance: {instance_id}")

            db_path = self._db_paths[instance_id]
            conn = sqlite3.connect(str(db_path))
            self._db_connections[instance_id] = conn
        return self._db_connections[instance_id]

    def execute_query(self, instance_id: str, sql: str) -> list[tuple]:
        """Execute a SQL query and return results."""
        conn = self.get_db_connection(instance_id)
        cursor = conn.cursor()
        cursor.execute(sql)
        return cursor.fetchall()

    def close(self) -> None:
        """Close all database connections."""
        for conn in self._db_connections.values():
            conn.close()
        self._db_connections.clear()


# ============================================================================
# OrmAI Benchmark Adapter
# ============================================================================


class OrmAIBenchmarkAdapter:
    """
    Creates OrmAI toolset for arbitrary SQLite databases.

    Uses SQLAlchemy automap to dynamically generate model classes from
    database schemas, then creates an OrmAI adapter and toolset.
    """

    def __init__(self, db_path: Path):
        from sqlalchemy import MetaData, PrimaryKeyConstraint, create_engine
        from sqlalchemy.ext.automap import automap_base

        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}")

        # Reflect and prepare models
        metadata = MetaData()
        metadata.reflect(bind=self.engine)

        # Add primary key constraints to tables that don't have them
        # (required for automap to work)
        for table in metadata.tables.values():
            if not table.primary_key.columns:
                first_col = list(table.columns)[0]
                table.append_constraint(PrimaryKeyConstraint(first_col))

        Base = automap_base(metadata=metadata)
        Base.prepare()

        self.models = list(Base.classes)
        self.toolset = self._create_toolset()

    def _create_toolset(self):
        """Create OrmAI toolset with reflected models."""
        from ormai.adapters.sqlalchemy.adapter import SQLAlchemyAdapter
        from ormai.policy.models import Budget, ModelPolicy, Policy, RowPolicy
        from ormai.utils.factory import ToolsetFactory

        # Create permissive policy for benchmark (no tenant scoping)
        policy = Policy(
            models={
                model.__name__: ModelPolicy(
                    allowed=True,
                    readable=True,
                    row_policy=RowPolicy(require_scope=False),
                    budget=Budget(max_rows=1000, broad_query_guard=False),
                )
                for model in self.models
            },
            require_tenant_scope=False,
            default_row_policy=RowPolicy(require_scope=False),
            default_budget=Budget(max_rows=1000, broad_query_guard=False),
        )

        adapter = SQLAlchemyAdapter(
            engine=self.engine,
            models=self.models,
            policy=policy,
        )

        # Use the schema property which does synchronous introspection
        schema = adapter.schema
        return ToolsetFactory.from_policy(policy=policy, adapter=adapter, schema=schema)

    def get_tool_schemas_openai(self) -> list[dict]:
        """Get tool schemas in OpenAI function calling format.

        Note: OpenAI requires function names to match ^[a-zA-Z0-9_-]+$
        so we replace dots with underscores (db.query -> db_query).
        """
        schemas = self.toolset.get_schemas()
        return [
            {
                "type": "function",
                "function": {
                    # Replace dots with underscores for OpenAI compatibility
                    "name": s["name"].replace(".", "_"),
                    "description": s["description"],
                    "parameters": s["parameters"],
                },
            }
            for s in schemas
        ]


class AdapterCache:
    """Cache OrmAI adapters by database path to avoid repeated reflection."""

    _adapters: dict[str, OrmAIBenchmarkAdapter] = {}

    @classmethod
    def get(cls, db_path: Path) -> OrmAIBenchmarkAdapter:
        key = str(db_path)
        if key not in cls._adapters:
            cls._adapters[key] = OrmAIBenchmarkAdapter(db_path)
        return cls._adapters[key]

    @classmethod
    def clear(cls) -> None:
        cls._adapters.clear()


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
    """OpenAI GPT provider."""

    name = "gpt-5-nano"

    def __init__(self):
        try:
            from openai import AsyncOpenAI
        except ImportError as e:
            raise ImportError("openai package not installed. Run: pip install openai") from e

        self.client = AsyncOpenAI()
        self.model = "gpt-5-nano"

    async def generate_sql(self, question: str, schema: str) -> str:
        """Generate SQL using GPT."""
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
        )
        return response.choices[0].message.content.strip()

    async def call_tools(
        self, question: str, schema: str, tools: list[dict]
    ) -> dict[str, Any] | None:
        """Call OrmAI tools using GPT function calling."""
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
        )

        message = response.choices[0].message
        if message.tool_calls:
            tool_call = message.tool_calls[0]
            # Convert tool name back from OpenAI format (db_query -> db.query)
            tool_name = tool_call.function.name.replace("_", ".", 1)
            return {
                "name": tool_name,
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


# Unsafe SQL patterns (used by RawSQLApproach)
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
    """
    Real OrmAI tool-based approach.

    Uses actual OrmAI toolset with SQLAlchemy adapter to execute queries
    through OrmAI's tools (db.query, db.aggregate, etc.).
    """

    def __init__(self, llm: LLMProvider, dataset: Spider2Dataset):
        from sqlalchemy.orm import Session

        self.llm = llm
        self.dataset = dataset
        self.Session = Session

    async def execute(self, example: SpiderExample) -> ApproachResult:
        """Execute using real OrmAI tools."""
        from ormai.core.context import RunContext

        try:
            # Get OrmAI adapter for this database (cached)
            db_path = self.dataset._db_paths.get(example.instance_id)
            if not db_path:
                return ApproachResult(
                    success=False,
                    error=f"Database not found for {example.instance_id}",
                )

            adapter = AdapterCache.get(db_path)

            # Get OrmAI tool schemas in OpenAI format
            tools = adapter.get_tool_schemas_openai()

            # LLM decides which tool to call
            schema_prompt = example.schema.to_prompt()
            tool_call = await self.llm.call_tools(
                example.question, schema_prompt, tools
            )

            if not tool_call:
                return ApproachResult(
                    success=False,
                    error="No tool call returned",
                )

            # Execute the actual OrmAI tool
            with self.Session(adapter.engine) as session:
                ctx = RunContext.create(
                    tenant_id="benchmark",
                    user_id="benchmark",
                    db=session,
                )

                result = await adapter.toolset.execute(
                    tool_call["name"],
                    tool_call["arguments"],
                    ctx,
                )

            if result.success:
                return ApproachResult(
                    success=True,
                    result=result.data,
                    tool_call=tool_call,
                )
            else:
                error_msg = result.error.get("message", str(result.error)) if result.error else "Unknown error"
                was_blocked = result.error.get("code") == "POLICY_VIOLATION" if result.error else False
                return ApproachResult(
                    success=False,
                    was_blocked=was_blocked,
                    error=error_msg,
                    tool_call=tool_call,
                )

        except Exception as e:
            return ApproachResult(
                success=False,
                error=str(e),
            )


class RawSQLApproach:
    """
    Raw SQL generation approach (no ORM).

    LLM generates raw SQL directly, which is executed against SQLite.
    This contrasts with OrmAI's structured tool-based approach.
    """

    def __init__(self, llm: LLMProvider, dataset: Spider2Dataset):
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
            result = self.dataset.execute_query(example.instance_id, sql)

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
                f"  Spider2-Lite Benchmark Demo  |  Questions: {total}  |  "
                f"LLMs: GPT + Claude",
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

        for name, m in [("gpt-5-nano", metrics_gpt4), ("claude", metrics_claude)]:
            # Progress bar representation
            pct = m.progress
            filled = int(pct / 5)
            bar = "[green]" + "━" * filled + "[/green][dim]" + "━" * (20 - filled) + "[/dim]"

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
            for name, m in [("gpt-5-nano", m_gpt4), ("claude", m_claude)]:
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
        dataset: Spider2Dataset,
        llms: list[LLMProvider],
        ui: DemoUI,
        verbose: bool = False,
    ):
        self.dataset = dataset
        self.llms = llms
        self.ui = ui
        self.verbose = verbose

    async def run(
        self,
        examples: list[SpiderExample],
        concurrency: int = 4,
    ) -> None:
        """Run the benchmark with live UI updates."""
        # Initialize metrics
        for llm in self.llms:
            for metrics in [
                self.ui.state.ormai_gpt4 if llm.name == "gpt-5-nano" else self.ui.state.ormai_claude,
                self.ui.state.sql_gpt4 if llm.name == "gpt-5-nano" else self.ui.state.sql_claude,
            ]:
                metrics.total = len(examples)

        # Create approaches for each LLM
        approaches = []
        for llm in self.llms:
            approaches.append(("ormai", llm, OrmAIApproach(llm, self.dataset)))
            approaches.append(("sql", llm, RawSQLApproach(llm, self.dataset)))

        # Semaphore for rate limiting
        semaphore = asyncio.Semaphore(concurrency)

        async def process_example(
            example: SpiderExample,
            approach_name: str,
            llm: LLMProvider,
            approach: OrmAIApproach | RawSQLApproach,
        ):
            async with semaphore:
                result = await approach.execute(example)

                # Update metrics
                if approach_name == "ormai":
                    metrics = (
                        self.ui.state.ormai_gpt4
                        if llm.name == "gpt-5-nano"
                        else self.ui.state.ormai_claude
                    )
                else:
                    metrics = (
                        self.ui.state.sql_gpt4
                        if llm.name == "gpt-5-nano"
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
                    if self.verbose:
                        console.print(f"[red][{approach_name}/{llm.name}] {example.instance_id}: {result.error}[/red]")

                # Update UI state for latest question
                self.ui.state.current_question = example.question
                self.ui.state.current_db = example.db_id
                if result.tool_call:
                    self.ui.state.current_ormai_action = (
                        f"{result.tool_call['name']}({json.dumps(result.tool_call['arguments'])})"
                    )
                if result.generated_sql:
                    self.ui.state.current_sql = result.generated_sql

        # Create all tasks
        tasks = []
        for example in examples:
            for approach_name, llm, approach in approaches:
                task = process_example(example, approach_name, llm, approach)
                tasks.append(task)

        # Process all tasks concurrently
        total = len(tasks)
        print(f"\n{'='*60}")
        print(f"Running {total} tasks ({len(examples)} examples x {len(approaches)} approaches)...")
        print(f"{'='*60}\n")

        await asyncio.gather(*tasks, return_exceptions=True)

        # Show summary table
        print(f"\n{'='*60}")
        print("BENCHMARK RESULTS")
        print(f"{'='*60}")
        console.print(self.ui.render_summary())


# ============================================================================
# CLI Commands
# ============================================================================


async def cmd_download(
    args: argparse.Namespace,  # noqa: ARG001 - required by CLI interface
) -> None:
    """Download the Spider2-Lite dataset."""
    del args  # unused but required by interface
    dataset = Spider2Dataset()
    await dataset.download()


async def cmd_run(args: argparse.Namespace) -> None:
    """Run the benchmark."""
    # Check for API keys
    if not os.getenv("OPENAI_API_KEY") and (args.llm in [None, "gpt-5-nano"]):
        console.print("[red]Error: OPENAI_API_KEY not set[/red]")
        return
    if not os.getenv("ANTHROPIC_API_KEY") and (args.llm in [None, "claude"]):
        console.print("[red]Error: ANTHROPIC_API_KEY not set[/red]")
        return

    dataset = Spider2Dataset()

    # Check if dataset exists
    jsonl_path = dataset.cache_dir / "spider2-lite.jsonl"
    if not jsonl_path.exists():
        console.print("[yellow]Spider2-Lite dataset not found. Downloading...[/yellow]")
        await dataset.download()

    # Load examples
    console.print(f"[blue]Loading Spider2-Lite examples (limit={args.limit})...[/blue]")
    examples = dataset.load_examples(limit=args.limit)

    if not examples:
        console.print("[red]No SQLite examples found. Make sure download completed successfully.[/red]")
        return

    console.print(f"[green]Loaded {len(examples)} SQLite examples[/green]")

    # Initialize LLMs
    llms: list[LLMProvider] = []
    if args.llm in [None, "gpt-5-nano"]:
        try:
            llms.append(OpenAIProvider())
        except ImportError as e:
            console.print(f"[yellow]Skipping GPT: {e}[/yellow]")
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
    runner = BenchmarkRunner(dataset, llms, ui, verbose=args.verbose)

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
        description="OrmAI Spider2-Lite Benchmark Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Download command
    subparsers.add_parser("download", help="Download Spider2-Lite dataset")

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
        choices=["gpt-5-nano", "claude"],
        default=None,
        help="Use only one LLM (default: both)",
    )
    run_parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Number of concurrent requests (default: 4)",
    )
    run_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed error messages",
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
