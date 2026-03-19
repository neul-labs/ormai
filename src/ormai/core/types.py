"""
Shared type definitions for OrmAI.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FieldType(str, Enum):
    """Supported field types."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    DATE = "date"
    TIME = "time"
    UUID = "uuid"
    JSON = "json"
    BINARY = "binary"
    UNKNOWN = "unknown"


class AggregateOp(str, Enum):
    """Supported aggregation operations."""

    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"


class RelationType(str, Enum):
    """Supported relation types."""

    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"
    MANY_TO_MANY = "many_to_many"


class FieldMetadata(BaseModel):
    """Metadata for a model field."""

    name: str
    field_type: str  # String to allow both enum values and raw strings
    nullable: bool = False
    primary_key: bool = False
    default: Any = None
    description: str | None = None

    model_config = {"frozen": True}


class RelationMetadata(BaseModel):
    """Metadata for a model relation."""

    name: str
    target_model: str
    relation_type: RelationType | str  # RelationType enum or string
    foreign_key: str | None = None
    back_populates: str | None = None

    model_config = {"frozen": True}


class ModelMetadata(BaseModel):
    """Metadata for a database model."""

    name: str
    table_name: str
    fields: dict[str, FieldMetadata] = Field(default_factory=dict)
    relations: dict[str, RelationMetadata] = Field(default_factory=dict)
    primary_key: str = "id"  # Primary key field name
    primary_keys: list[str] = Field(default_factory=list)  # For composite keys
    description: str | None = None

    model_config = {"frozen": True}


class SchemaMetadata(BaseModel):
    """Complete schema metadata for all models."""

    models: dict[str, ModelMetadata] = Field(default_factory=dict)

    model_config = {"frozen": True}

    def get_model(self, name: str) -> ModelMetadata | None:
        """Get metadata for a specific model."""
        return self.models.get(name)

    def list_models(self) -> list[str]:
        """List all model names."""
        return list(self.models.keys())
