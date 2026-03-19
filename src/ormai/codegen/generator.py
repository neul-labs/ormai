"""
Base code generator.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from ormai.core.types import SchemaMetadata
from ormai.policy.models import Policy


@dataclass
class GeneratedFile:
    """A generated source file."""

    path: str
    content: str
    module_name: str


@dataclass
class GenerationResult:
    """Result of code generation."""

    files: list[GeneratedFile] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def write_all(self, base_dir: Path | str) -> list[Path]:
        """
        Write all generated files to disk.

        Args:
            base_dir: Base directory to write files to

        Returns:
            List of paths to written files
        """
        base_path = Path(base_dir)
        written = []

        for gf in self.files:
            file_path = base_path / gf.path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(gf.content)
            written.append(file_path)

        return written


class CodeGenerator(ABC):
    """
    Abstract base class for code generators.

    Code generators take schema metadata and policy configuration
    and produce Python source code.
    """

    def __init__(self, schema: SchemaMetadata, policy: Policy) -> None:
        """
        Initialize the generator.

        Args:
            schema: Database schema metadata
            policy: Policy configuration
        """
        self.schema = schema
        self.policy = policy

    @abstractmethod
    def generate(self) -> GenerationResult:
        """
        Generate source code.

        Returns:
            GenerationResult containing generated files and any warnings
        """
        ...

    def _indent(self, text: str, spaces: int = 4) -> str:
        """Indent text by a number of spaces."""
        prefix = " " * spaces
        return "\n".join(prefix + line if line else line for line in text.split("\n"))

    def _format_docstring(self, text: str, indent: int = 4) -> str:
        """Format a docstring with proper indentation."""
        lines = text.strip().split("\n")
        if len(lines) == 1:
            return f'"""{lines[0]}"""'
        else:
            prefix = " " * indent
            formatted = ['"""']
            formatted.extend(lines)
            formatted.append('"""')
            return "\n".join(prefix + line if i > 0 else line for i, line in enumerate(formatted))
