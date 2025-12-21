"""
SQLAlchemy schema introspection.

Extracts metadata from SQLAlchemy models to build the schema representation.
"""

from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm import RelationshipProperty
from sqlalchemy.sql.sqltypes import (
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    LargeBinary,
    String,
    Text,
    Time,
)

from ormai.core.types import (
    FieldMetadata,
    FieldType,
    ModelMetadata,
    RelationMetadata,
    SchemaMetadata,
)


class SQLAlchemyIntrospector:
    """
    Introspects SQLAlchemy models to extract schema metadata.
    """

    def __init__(self, models: list[type]) -> None:
        """
        Initialize with a list of SQLAlchemy model classes.

        Args:
            models: List of SQLAlchemy declarative model classes
        """
        self.models = models
        self._model_map: dict[str, type] = {
            self._get_model_name(m): m for m in models
        }

    def introspect(self) -> SchemaMetadata:
        """
        Introspect all registered models and return schema metadata.
        """
        models_meta: dict[str, ModelMetadata] = {}

        for model in self.models:
            model_name = self._get_model_name(model)
            models_meta[model_name] = self._introspect_model(model)

        return SchemaMetadata(models=models_meta)

    def _get_model_name(self, model: type) -> str:
        """Get the name to use for a model."""
        return model.__name__

    def _introspect_model(self, model: type) -> ModelMetadata:
        """Introspect a single model."""
        mapper = inspect(model)

        # Get table name
        table_name = mapper.mapped_table.name

        # Get fields
        fields: dict[str, FieldMetadata] = {}
        primary_keys: list[str] = []

        for column in mapper.columns:
            field_meta = self._introspect_column(column)
            fields[column.key] = field_meta
            if column.primary_key:
                primary_keys.append(column.key)

        # Get relations
        relations: dict[str, RelationMetadata] = {}
        for rel in mapper.relationships:
            rel_meta = self._introspect_relationship(rel)
            relations[rel.key] = rel_meta

        return ModelMetadata(
            name=self._get_model_name(model),
            table_name=table_name,
            fields=fields,
            relations=relations,
            primary_keys=primary_keys,
            description=model.__doc__,
        )

    def _introspect_column(self, column: Any) -> FieldMetadata:
        """Introspect a single column."""
        return FieldMetadata(
            name=column.key,
            field_type=self._get_field_type(column.type),
            nullable=column.nullable or False,
            primary_key=column.primary_key,
            default=self._get_default(column),
            description=column.doc,
        )

    def _introspect_relationship(self, rel: RelationshipProperty) -> RelationMetadata:
        """Introspect a relationship."""
        # Determine relationship type
        if rel.uselist:
            if rel.secondary is not None:
                rel_type = "many_to_many"
            else:
                rel_type = "one_to_many"
        else:
            rel_type = "many_to_one"

        # Get foreign key if available
        foreign_key = None
        if rel.local_columns:
            fk_cols = list(rel.local_columns)
            if fk_cols:
                foreign_key = fk_cols[0].key

        return RelationMetadata(
            name=rel.key,
            target_model=rel.mapper.class_.__name__,
            relation_type=rel_type,
            foreign_key=foreign_key,
            back_populates=rel.back_populates,
        )

    def _get_field_type(self, sa_type: Any) -> FieldType:
        """Map SQLAlchemy type to OrmAI FieldType."""
        type_mapping = {
            String: FieldType.STRING,
            Text: FieldType.STRING,
            Integer: FieldType.INTEGER,
            Float: FieldType.FLOAT,
            Boolean: FieldType.BOOLEAN,
            DateTime: FieldType.DATETIME,
            Date: FieldType.DATE,
            Time: FieldType.TIME,
            LargeBinary: FieldType.BINARY,
        }

        for sa_class, field_type in type_mapping.items():
            if isinstance(sa_type, sa_class):
                return field_type

        # Check for UUID
        type_name = type(sa_type).__name__.lower()
        if "uuid" in type_name:
            return FieldType.UUID
        if "json" in type_name:
            return FieldType.JSON

        return FieldType.UNKNOWN

    def _get_default(self, column: Any) -> Any:
        """Extract default value from column if available."""
        if column.default is None:
            return None
        if column.default.is_scalar:
            return column.default.arg
        # For callable defaults, we can't represent them
        return None

    def get_model_class(self, name: str) -> type | None:
        """Get the model class by name."""
        return self._model_map.get(name)
