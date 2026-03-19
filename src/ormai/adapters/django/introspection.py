"""
Django model introspection.

Extracts schema metadata from Django models.
"""

from typing import Any

from django.db import models
from django.db.models import Field
from django.db.models.fields.related import ForeignKey, ManyToManyField, OneToOneField

from ormai.core.types import (
    FieldMetadata,
    ModelMetadata,
    RelationMetadata,
    SchemaMetadata,
)


class DjangoIntrospector:
    """
    Introspects Django models to extract schema metadata.

    Usage:
        from django.apps import apps
        introspector = DjangoIntrospector(apps.get_app_config('myapp'))
        schema = introspector.introspect()
    """

    # Map Django field types to OrmAI types
    TYPE_MAP = {
        "AutoField": "integer",
        "BigAutoField": "integer",
        "SmallAutoField": "integer",
        "IntegerField": "integer",
        "SmallIntegerField": "integer",
        "BigIntegerField": "integer",
        "PositiveIntegerField": "integer",
        "PositiveSmallIntegerField": "integer",
        "PositiveBigIntegerField": "integer",
        "FloatField": "float",
        "DecimalField": "decimal",
        "CharField": "string",
        "TextField": "string",
        "EmailField": "string",
        "URLField": "string",
        "SlugField": "string",
        "UUIDField": "string",
        "BooleanField": "boolean",
        "NullBooleanField": "boolean",
        "DateField": "date",
        "DateTimeField": "datetime",
        "TimeField": "time",
        "DurationField": "string",
        "BinaryField": "bytes",
        "FileField": "string",
        "ImageField": "string",
        "JSONField": "json",
        "GenericIPAddressField": "string",
    }

    def __init__(
        self,
        app_config: Any = None,
        models_list: list[type[models.Model]] | None = None,
    ) -> None:
        """
        Initialize the introspector.

        Args:
            app_config: Django AppConfig to introspect
            models_list: Explicit list of models to introspect
        """
        self.app_config = app_config
        self._models_list = models_list or []

    def get_models(self) -> list[type[models.Model]]:
        """Get all models to introspect."""
        if self._models_list:
            return self._models_list

        if self.app_config:
            return list(self.app_config.get_models())

        return []

    def get_model_map(self) -> dict[str, type[models.Model]]:
        """Get a map of model names to model classes."""
        return {m.__name__: m for m in self.get_models()}

    def introspect(self) -> SchemaMetadata:
        """
        Introspect all models and return schema metadata.

        Returns a SchemaMetadata containing all model information.
        """
        models_meta = {}

        for model in self.get_models():
            model_name = model.__name__
            models_meta[model_name] = self._introspect_model(model)

        return SchemaMetadata(models=models_meta)

    def _introspect_model(self, model: type[models.Model]) -> ModelMetadata:
        """Introspect a single Django model."""
        fields = {}
        relations = {}
        pk_field = None

        # Process regular fields
        for field in model._meta.get_fields():
            if isinstance(field, (ForeignKey, ManyToManyField, OneToOneField)):
                # Handle relations separately
                rel_meta = self._introspect_relation(field)
                if rel_meta:
                    relations[field.name] = rel_meta
            elif isinstance(field, Field):
                # Regular field
                field_meta = self._introspect_field(field)
                fields[field.name] = field_meta

                if field.primary_key:
                    pk_field = field.name

        # Also check for reverse relations
        for rel in model._meta.get_fields():
            if hasattr(rel, "related_model") and hasattr(rel, "field"):
                if rel.name not in relations:
                    # This is a reverse relation
                    rel_meta = self._introspect_reverse_relation(rel)
                    if rel_meta:
                        relations[rel.name] = rel_meta

        return ModelMetadata(
            name=model.__name__,
            table_name=model._meta.db_table,
            fields=fields,
            relations=relations,
            primary_key=pk_field,
        )

    def _introspect_field(self, field: Field) -> FieldMetadata:
        """Introspect a Django field."""
        field_type = field.__class__.__name__
        orm_type = self.TYPE_MAP.get(field_type, "string")

        return FieldMetadata(
            name=field.name,
            type=orm_type,
            nullable=field.null,
            primary_key=field.primary_key,
            unique=field.unique,
            default=self._get_default(field),
        )

    def _introspect_relation(self, field: Any) -> RelationMetadata | None:
        """Introspect a relation field."""
        if isinstance(field, ForeignKey):
            return RelationMetadata(
                name=field.name,
                target_model=field.related_model.__name__,
                relation_type="many_to_one",
                foreign_key=field.column,
            )
        elif isinstance(field, OneToOneField):
            return RelationMetadata(
                name=field.name,
                target_model=field.related_model.__name__,
                relation_type="one_to_one",
                foreign_key=field.column,
            )
        elif isinstance(field, ManyToManyField):
            return RelationMetadata(
                name=field.name,
                target_model=field.related_model.__name__,
                relation_type="many_to_many",
            )
        return None

    def _introspect_reverse_relation(self, rel: Any) -> RelationMetadata | None:
        """Introspect a reverse relation."""
        if not hasattr(rel, "related_model"):
            return None

        return RelationMetadata(
            name=rel.name or f"{rel.related_model.__name__.lower()}_set",
            target_model=rel.related_model.__name__,
            relation_type="one_to_many",
        )

    def _get_default(self, field: Field) -> Any:
        """Get the default value for a field."""
        if field.has_default():
            default = field.get_default()
            # Don't return callable defaults
            if callable(default):
                return None
            return default
        return None
