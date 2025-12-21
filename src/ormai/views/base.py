"""
Base view model utilities.
"""

from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T", bound="BaseView")


class BaseView(BaseModel):
    """
    Base class for all OrmAI view models.

    Views are Pydantic models that represent the public API of database entities.
    They handle serialization, validation, and provide a stable schema for LLMs.
    """

    model_config = ConfigDict(
        from_attributes=True,  # Allow creating from ORM objects
        frozen=True,  # Views are immutable
        extra="ignore",  # Ignore extra fields from ORM
    )

    @classmethod
    def from_orm(cls: type[T], obj: Any) -> T:
        """Create a view from an ORM object."""
        return cls.model_validate(obj)

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        """Create a view from a dictionary."""
        return cls.model_validate(data)

    def to_dict(self) -> dict[str, Any]:
        """Convert view to a dictionary."""
        return self.model_dump()


def view_from_dict(data: dict[str, Any], view_class: type[T] | None = None) -> T | dict[str, Any]:
    """
    Convert a dictionary to a view model if a class is provided.

    If no view class is provided, returns the dictionary as-is.
    """
    if view_class is None:
        return data
    return view_class.model_validate(data)
