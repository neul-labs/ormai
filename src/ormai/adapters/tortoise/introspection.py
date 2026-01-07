"""
Tortoise ORM schema introspection.

Extracts schema metadata from Tortoise model definitions.
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


class TortoiseIntrospector:
    """
    Introspects Tortoise ORM models to build schema metadata.
    """

    def __init__(self, models: list[type]) -> None:
        """
        Initialize the introspector.

        Args:
            models: List of Tortoise model classes
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
        """Introspect a single Tortoise model."""
        from tortoise.fields.relational import (
            BackwardFKRelation,
            BackwardOneToOneRelation,
        )
        from tortoise.models import Model

        if not issubclass(model, Model):
            raise ValueError(f"{model} is not a Tortoise Model")

        meta = model._meta

        # Get fields
        fields_meta: dict[str, FieldMetadata] = {}
        for field_name, field_obj in meta.fields_map.items():
            # Skip reverse relations
            if isinstance(field_obj, (BackwardFKRelation, BackwardOneToOneRelation)):
                continue

            field_meta = self._introspect_field(field_name, field_obj)
            if field_meta:
                fields_meta[field_name] = field_meta

        # Get relations
        relations_meta: dict[str, RelationMetadata] = {}
        for field_name, field_obj in meta.fields_map.items():
            rel_meta = self._introspect_relation(field_name, field_obj, model)
            if rel_meta:
                relations_meta[field_name] = rel_meta

        # Find primary key
        pk_field = meta.pk_attr or "id"

        return ModelMetadata(
            name=model.__name__,
            table_name=meta.db_table or model.__name__.lower(),
            fields=fields_meta,
            relations=relations_meta,
            primary_key=pk_field,
        )

    def _introspect_field(self, name: str, field: Any) -> FieldMetadata | None:
        """Introspect a single field."""
        from tortoise import fields as tortoise_fields
        from tortoise.fields.relational import (
            BackwardFKRelation,
            BackwardOneToOneRelation,
            ForeignKeyFieldInstance,
            ManyToManyFieldInstance,
            OneToOneFieldInstance,
        )

        # Map Tortoise field types to our type system
        type_map: dict[type, str] = {
            tortoise_fields.IntField: "integer",
            tortoise_fields.BigIntField: "bigint",
            tortoise_fields.SmallIntField: "smallint",
            tortoise_fields.CharField: "string",
            tortoise_fields.TextField: "text",
            tortoise_fields.BooleanField: "boolean",
            tortoise_fields.DecimalField: "decimal",
            tortoise_fields.FloatField: "float",
            tortoise_fields.DateField: "date",
            tortoise_fields.DatetimeField: "datetime",
            tortoise_fields.TimeField: "time",
            tortoise_fields.UUIDField: "uuid",
            tortoise_fields.JSONField: "json",
            tortoise_fields.BinaryField: "binary",
        }

        # Handle relation fields separately
        if isinstance(field, (
            ForeignKeyFieldInstance,
            OneToOneFieldInstance,
            ManyToManyFieldInstance,
            BackwardFKRelation,
            BackwardOneToOneRelation,
        )):
            return None

        # Get the field type
        field_type = "unknown"
        for field_class, type_name in type_map.items():
            if isinstance(field, field_class):
                field_type = type_name
                break

        # Check if it's a primary key
        is_pk = getattr(field, "primary_key", False) or getattr(field, "pk", False)

        # Check if nullable
        nullable = getattr(field, "null", False)

        return FieldMetadata(
            name=name,
            field_type=field_type,
            nullable=nullable,
            primary_key=is_pk,
        )

    def _introspect_relation(
        self, name: str, field: Any, model: type  # noqa: ARG002
    ) -> RelationMetadata | None:
        """Introspect a relation field."""
        from tortoise.fields.relational import (
            BackwardFKRelation,
            BackwardOneToOneRelation,
            ForeignKeyFieldInstance,
            ManyToManyFieldInstance,
            OneToOneFieldInstance,
        )

        if isinstance(field, ForeignKeyFieldInstance):
            related_model = field.related_model
            return RelationMetadata(
                name=name,
                relation_type=RelationType.MANY_TO_ONE,
                target_model=related_model.__name__ if related_model else "Unknown",
                foreign_key=f"{name}_id",
            )

        if isinstance(field, OneToOneFieldInstance):
            related_model = field.related_model
            return RelationMetadata(
                name=name,
                relation_type=RelationType.ONE_TO_ONE,
                target_model=related_model.__name__ if related_model else "Unknown",
                foreign_key=f"{name}_id",
            )

        if isinstance(field, ManyToManyFieldInstance):
            related_model = field.related_model
            return RelationMetadata(
                name=name,
                relation_type=RelationType.MANY_TO_MANY,
                target_model=related_model.__name__ if related_model else "Unknown",
            )

        if isinstance(field, BackwardFKRelation):
            related_model = field.related_model
            return RelationMetadata(
                name=name,
                relation_type=RelationType.ONE_TO_MANY,
                target_model=related_model.__name__ if related_model else "Unknown",
            )

        if isinstance(field, BackwardOneToOneRelation):
            related_model = field.related_model
            return RelationMetadata(
                name=name,
                relation_type=RelationType.ONE_TO_ONE,
                target_model=related_model.__name__ if related_model else "Unknown",
            )

        return None
