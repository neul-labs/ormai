"""
OrmAI configuration for the example app.
"""

from app.database import engine
from app.models import ALL_MODELS
from ormai.quickstart import mount_sqlalchemy
from ormai.utils.defaults import DEFAULT_PROD


def setup_ormai():
    """
    Set up OrmAI for the application.

    Returns an OrmAIMount with all configured components.
    """
    ormai = mount_sqlalchemy(
        engine=engine,
        models=ALL_MODELS,
        tenant_field="tenant_id",
        profile=DEFAULT_PROD,
        enable_mcp=True,
        audit_path="./audit.jsonl",
        # Mask sensitive fields
        mask_fields=["email", "phone"],
    )

    return ormai


# Global OrmAI instance
ormai = setup_ormai()
