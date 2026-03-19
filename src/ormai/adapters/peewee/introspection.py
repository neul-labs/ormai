"""
Peewee schema introspection.

Extracts schema metadata from Peewee model definitions.
"""

from __future__ import annotations

from typing import Any

from ormai.core.types import (
    FieldMetadata,
    ModelMetadata,
    RelationMetadata,
    RelationType,
    SchemaMetadata,
)


class PeeweeIntrospector:
    """
    Introspects Peewee models to build schema metadata.
    """

    def __init__(self, models: list[type]) -> None:
        """
        Initialize the introspector.

        Args:
            models: List of Peewee model classes
        """
        self.models = models

    def introspect(self) -> SchemaMetadata:
        """
        Introspect all registered models and build schema metadata.
        """
        model_metadata: dict[str, ModelMetadata] = {}

        for model in self.models:
            model_meta = self._introspect_model(model)
            model_metadata[model_meta.name] = model_meta

        return SchemaMetadata(models=model_metadata)

    def _introspect_model(self, model: type) -> ModelMetadata:
        """Introspect a single Peewee model."""
        from peewee import Model

        if not issubclass(model, Model):
            raise ValueError(f"{model} is not a Peewee Model")

        meta = model._meta

        # Get fields
        fields_meta: dict[str, FieldMetadata] = {}
        relations_meta: dict[str, RelationMetadata] = {}

        for field_name, field_obj in meta.fields.items():
            # Check if it's a foreign key
            rel_meta = self._introspect_relation(field_name, field_obj)
            if rel_meta:
                relations_meta[field_name] = rel_meta
            else:
                field_meta = self._introspect_field(field_name, field_obj)
                if field_meta:
                    fields_meta[field_name] = field_meta

        # Also add foreign key fields as regular fields for filtering
        for field_name, field_obj in meta.fields.items():
            if self._is_foreign_key(field_obj):
                # Add the _id field
                fk_field_name = field_obj.column_name or f"{field_name}_id"
                fields_meta[fk_field_name] = FieldMetadata(
                    name=fk_field_name,
                    field_type="integer",
                    nullable=field_obj.null,
                    primary_key=False,
                )

        # Find primary key
        pk_field = meta.primary_key.name if meta.primary_key else "id"

        return ModelMetadata(
            name=model.__name__,
            table_name=meta.table_name,
            fields=fields_meta,
            relations=relations_meta,
            primary_key=pk_field,
        )

    def _introspect_field(self, name: str, field: Any) -> FieldMetadata | None:
        """Introspect a single field."""
        from peewee import (
            BigIntegerField,
            BlobField,
            BooleanField,
            CharField,
            DateField,
            DateTimeField,
            DecimalField,
            DoubleField,
            FloatField,
            ForeignKeyField,
            IntegerField,
            SmallIntegerField,
            TextField,
            TimeField,
            UUIDField,
        )

        # Skip foreign keys (handled separately)
        if isinstance(field, ForeignKeyField):
            return None

        # Map Peewee field types to our type system
        type_map: dict[type, str] = {
            IntegerField: "integer",
            BigIntegerField: "bigint",
            SmallIntegerField: "smallint",
            CharField: "string",
            TextField: "text",
            BooleanField: "boolean",
            DecimalField: "decimal",
            FloatField: "float",
            DoubleField: "float",
            DateField: "date",
            DateTimeField: "datetime",
            TimeField: "time",
            UUIDField: "uuid",
            BlobField: "binary",
        }

        # Get the field type
        field_type = "unknown"
        for field_class, type_name in type_map.items():
            if isinstance(field, field_class):
                field_type = type_name
                break

        # Check if it's a primary key
        is_pk = getattr(field, "primary_key", False)

        # Check if nullable
        nullable = getattr(field, "null", False)

        return FieldMetadata(
            name=name,
            field_type=field_type,
            nullable=nullable,
            primary_key=is_pk,
        )

    def _introspect_relation(
        self, name: str, field: Any
    ) -> RelationMetadata | None:
        """Introspect a relation field."""
        from peewee import ForeignKeyField

        if isinstance(field, ForeignKeyField):
            related_model = field.rel_model
            return RelationMetadata(
                name=name,
                relation_type=RelationType.MANY_TO_ONE,
                target_model=related_model.__name__,
                foreign_key=field.column_name or f"{name}_id",
            )

        return None

    def _is_foreign_key(self, field: Any) -> bool:
        """Check if a field is a foreign key."""
        from peewee import ForeignKeyField
        return isinstance(field, ForeignKeyField)
