"""
View model factory.

Generates Pydantic view models dynamically from ORM schema and policy.
"""

from typing import Any

from pydantic import create_model
from pydantic.fields import FieldInfo

from ormai.core.types import FieldMetadata, FieldType, ModelMetadata, SchemaMetadata
from ormai.policy.models import FieldAction, ModelPolicy, Policy
from ormai.views.base import BaseView


class ViewFactory:
    """
    Factory for generating Pydantic view models from schema and policy.

    Generated views:
    - Only include allowed fields
    - Have correct types based on ORM column types
    - Are properly typed for IDE support
    - Can be used for both input validation and output serialization
    """

    # Mapping from OrmAI field types to Python types
    TYPE_MAPPING: dict[FieldType, type] = {
        FieldType.STRING: str,
        FieldType.INTEGER: int,
        FieldType.FLOAT: float,
        FieldType.BOOLEAN: bool,
        FieldType.DATETIME: str,  # ISO format string
        FieldType.DATE: str,  # ISO format string
        FieldType.TIME: str,  # ISO format string
        FieldType.UUID: str,
        FieldType.JSON: dict,
        FieldType.BINARY: bytes,
        FieldType.UNKNOWN: Any,
    }

    def __init__(self, schema: SchemaMetadata, policy: Policy) -> None:
        """
        Initialize the factory.

        Args:
            schema: Database schema metadata
            policy: Policy configuration
        """
        self.schema = schema
        self.policy = policy
        self._cache: dict[str, type[BaseView]] = {}

    def get_view(self, model_name: str) -> type[BaseView]:
        """
        Get or create a view class for a model.

        Returns a dynamically generated Pydantic model class.
        """
        if model_name in self._cache:
            return self._cache[model_name]

        model_meta = self.schema.get_model(model_name)
        if model_meta is None:
            raise ValueError(f"Model not found: {model_name}")

        model_policy = self.policy.get_model_policy(model_name)
        view_class = self._create_view(model_name, model_meta, model_policy)
        self._cache[model_name] = view_class
        return view_class

    def get_all_views(self) -> dict[str, type[BaseView]]:
        """
        Generate view classes for all allowed models.

        Returns a dict mapping model names to view classes.
        """
        views = {}
        for model_name in self.policy.list_allowed_models():
            views[model_name] = self.get_view(model_name)
        return views

    def _create_view(
        self,
        model_name: str,
        model_meta: ModelMetadata,
        model_policy: ModelPolicy | None,
    ) -> type[BaseView]:
        """Create a view class for a model."""
        fields: dict[str, tuple[type, FieldInfo]] = {}

        for field_name, field_meta in model_meta.fields.items():
            # Check if field is allowed by policy
            if model_policy:
                field_policy = model_policy.get_field_policy(field_name)
                if field_policy.action == FieldAction.DENY:
                    continue

            # Get Python type
            python_type = self._get_python_type(field_meta)

            # Make nullable fields Optional
            if field_meta.nullable:
                python_type = python_type | None  # type: ignore

            # Create field info
            field_info = FieldInfo(
                default=None if field_meta.nullable else ...,
                description=field_meta.description,
            )

            fields[field_name] = (python_type, field_info)

        # Create the model class
        view_class = create_model(
            f"{model_name}View",
            __base__=BaseView,
            **fields,  # type: ignore
        )

        return view_class  # type: ignore

    def _get_python_type(self, field_meta: FieldMetadata) -> type:
        """Get the Python type for a field."""
        return self.TYPE_MAPPING.get(field_meta.field_type, Any)

    @classmethod
    def from_policy(
        cls,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> "ViewFactory":
        """
        Create a ViewFactory from policy and schema.

        This is the main entry point for creating view factories.
        """
        return cls(schema=schema, policy=policy)
