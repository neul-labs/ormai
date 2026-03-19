"""
View model code generator.

Generates Pydantic view model source files from ORM metadata and policies.
"""

from datetime import datetime

from ormai.codegen.generator import CodeGenerator, GeneratedFile, GenerationResult
from ormai.core.types import FieldMetadata, FieldType, ModelMetadata, SchemaMetadata
from ormai.policy.models import FieldAction, ModelPolicy, Policy


class ViewCodeGenerator(CodeGenerator):
    """
    Generates Pydantic view model source code.

    Produces Python files with properly typed view models that:
    - Only include allowed fields (per policy)
    - Have correct type annotations
    - Include docstrings with field descriptions
    - Support IDE autocompletion and type checking

    Example output:
        class CustomerView(BaseView):
            '''View model for Customer.'''

            id: int
            name: str
            email: str | None = None
            created_at: datetime
    """

    # Mapping from OrmAI field types to Python type annotations
    TYPE_ANNOTATIONS: dict[FieldType, str] = {
        FieldType.STRING: "str",
        FieldType.INTEGER: "int",
        FieldType.FLOAT: "float",
        FieldType.BOOLEAN: "bool",
        FieldType.DATETIME: "datetime",
        FieldType.DATE: "date",
        FieldType.TIME: "time",
        FieldType.UUID: "UUID",
        FieldType.JSON: "dict[str, Any]",
        FieldType.BINARY: "bytes",
        FieldType.UNKNOWN: "Any",
    }

    def __init__(
        self,
        schema: SchemaMetadata,
        policy: Policy,
        *,
        module_name: str = "views",
        include_create_views: bool = True,
        include_update_views: bool = True,
    ) -> None:
        """
        Initialize the generator.

        Args:
            schema: Database schema metadata
            policy: Policy configuration
            module_name: Name for the generated module
            include_create_views: Generate input views for create operations
            include_update_views: Generate input views for update operations
        """
        super().__init__(schema, policy)
        self.module_name = module_name
        self.include_create_views = include_create_views
        self.include_update_views = include_update_views

    def generate(self) -> GenerationResult:
        """Generate view model source files."""
        result = GenerationResult()

        # Generate main views file
        views_content = self._generate_views_file()
        result.files.append(GeneratedFile(
            path=f"{self.module_name}.py",
            content=views_content,
            module_name=self.module_name,
        ))

        return result

    def _generate_views_file(self) -> str:
        """Generate the main views file content."""
        lines = [
            '"""',
            "Auto-generated view models.",
            "",
            f"Generated at: {datetime.utcnow().isoformat()}",
            "Do not edit manually - regenerate from schema/policy changes.",
            '"""',
            "",
            "from __future__ import annotations",
            "",
            "from datetime import date, datetime, time",
            "from typing import Any",
            "from uuid import UUID",
            "",
            "from pydantic import BaseModel, ConfigDict, Field",
            "",
            "",
            "class BaseView(BaseModel):",
            '    """Base class for all view models."""',
            "",
            "    model_config = ConfigDict(",
            "        from_attributes=True,",
            "        frozen=True,",
            '        extra="ignore",',
            "    )",
            "",
        ]

        # Generate view for each allowed model
        for model_name in self.policy.list_allowed_models():
            model_meta = self.schema.get_model(model_name)
            if model_meta is None:
                result_warnings = [f"Model {model_name} not found in schema"]
                continue

            model_policy = self.policy.get_model_policy(model_name)

            # Main view (for reads)
            lines.extend(self._generate_view_class(
                model_name, model_meta, model_policy, suffix="View"
            ))
            lines.append("")

            # Create view (for create input)
            if self.include_create_views and model_policy and model_policy.writable:
                lines.extend(self._generate_create_view(
                    model_name, model_meta, model_policy
                ))
                lines.append("")

            # Update view (for update input)
            if self.include_update_views and model_policy and model_policy.writable:
                lines.extend(self._generate_update_view(
                    model_name, model_meta, model_policy
                ))
                lines.append("")

        return "\n".join(lines)

    def _generate_view_class(
        self,
        model_name: str,
        model_meta: ModelMetadata,
        model_policy: ModelPolicy | None,
        suffix: str = "View",
    ) -> list[str]:
        """Generate a single view class."""
        class_name = f"{model_name}{suffix}"
        lines = [
            f"class {class_name}(BaseView):",
            f'    """View model for {model_name}."""',
            "",
        ]

        field_lines = []
        for field_name, field_meta in model_meta.fields.items():
            # Check if field is allowed
            if model_policy:
                field_policy = model_policy.get_field_policy(field_name)
                if field_policy.action == FieldAction.DENY:
                    continue

            field_line = self._generate_field(field_name, field_meta)
            field_lines.append(field_line)

        if field_lines:
            lines.extend(f"    {line}" for line in field_lines)
        else:
            lines.append("    pass")

        return lines

    def _generate_create_view(
        self,
        model_name: str,
        model_meta: ModelMetadata,
        model_policy: ModelPolicy,
    ) -> list[str]:
        """Generate a create input view."""
        class_name = f"{model_name}Create"
        lines = [
            f"class {class_name}(BaseModel):",
            f'    """Input model for creating {model_name}."""',
            "",
            "    model_config = ConfigDict(extra=\"forbid\")",
            "",
        ]

        field_lines = []
        readonly_fields = set()
        if model_policy.write_policy:
            readonly_fields = set(model_policy.write_policy.readonly_fields)

        for field_name, field_meta in model_meta.fields.items():
            # Skip readonly fields and auto-generated fields
            if field_name in readonly_fields:
                continue
            if field_name in ("id", "created_at", "updated_at"):
                continue

            # Check if field is allowed
            field_policy = model_policy.get_field_policy(field_name)
            if field_policy.action == FieldAction.DENY:
                continue

            field_line = self._generate_field(field_name, field_meta, for_input=True)
            field_lines.append(field_line)

        if field_lines:
            lines.extend(f"    {line}" for line in field_lines)
        else:
            lines.append("    pass")

        return lines

    def _generate_update_view(
        self,
        model_name: str,
        model_meta: ModelMetadata,
        model_policy: ModelPolicy,
    ) -> list[str]:
        """Generate an update input view (all fields optional)."""
        class_name = f"{model_name}Update"
        lines = [
            f"class {class_name}(BaseModel):",
            f'    """Input model for updating {model_name}."""',
            "",
            "    model_config = ConfigDict(extra=\"forbid\")",
            "",
        ]

        field_lines = []
        readonly_fields = set()
        if model_policy.write_policy:
            readonly_fields = set(model_policy.write_policy.readonly_fields)

        for field_name, field_meta in model_meta.fields.items():
            # Skip readonly fields and auto-generated fields
            if field_name in readonly_fields:
                continue
            if field_name in ("id", "created_at", "updated_at"):
                continue

            # Check if field is allowed
            field_policy = model_policy.get_field_policy(field_name)
            if field_policy.action == FieldAction.DENY:
                continue

            # All update fields are optional
            field_line = self._generate_field(
                field_name, field_meta, for_input=True, optional=True
            )
            field_lines.append(field_line)

        if field_lines:
            lines.extend(f"    {line}" for line in field_lines)
        else:
            lines.append("    pass")

        return lines

    def _generate_field(
        self,
        field_name: str,
        field_meta: FieldMetadata,
        for_input: bool = False,
        optional: bool = False,
    ) -> str:
        """Generate a field definition line."""
        # Get type annotation
        type_str = self._get_type_annotation(field_meta.field_type)

        # Handle nullable/optional
        is_optional = field_meta.nullable or optional
        if is_optional:
            type_str = f"{type_str} | None"

        # Build field definition
        if is_optional:
            default = "None"
        elif field_meta.default is not None:
            default = "..."  # Required but has DB default
        else:
            default = "..."

        # Add Field() with description if available
        if field_meta.description:
            return f'{field_name}: {type_str} = Field({default}, description="{field_meta.description}")'
        elif is_optional:
            return f"{field_name}: {type_str} = {default}"
        else:
            return f"{field_name}: {type_str}"

    def _get_type_annotation(self, field_type: FieldType | str) -> str:
        """Get Python type annotation for a field type."""
        if isinstance(field_type, str):
            # Handle string field types (from some adapters)
            field_type_lower = field_type.lower()
            if "int" in field_type_lower:
                return "int"
            elif "float" in field_type_lower or "decimal" in field_type_lower:
                return "float"
            elif "bool" in field_type_lower:
                return "bool"
            elif "datetime" in field_type_lower:
                return "datetime"
            elif "date" in field_type_lower:
                return "date"
            elif "time" in field_type_lower:
                return "time"
            elif "uuid" in field_type_lower:
                return "UUID"
            elif "json" in field_type_lower:
                return "dict[str, Any]"
            elif "bytes" in field_type_lower or "binary" in field_type_lower:
                return "bytes"
            else:
                return "str"

        return self.TYPE_ANNOTATIONS.get(field_type, "Any")
