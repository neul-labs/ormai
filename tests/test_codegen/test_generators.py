"""Tests for code generators."""

import pytest

from ormai.codegen.views import ViewCodeGenerator
from ormai.codegen.tools import DomainToolGenerator
from ormai.core.types import FieldMetadata, FieldType, ModelMetadata, SchemaMetadata
from ormai.policy.models import FieldAction, FieldPolicy, ModelPolicy, Policy, WritePolicy


@pytest.fixture
def sample_schema() -> SchemaMetadata:
    """Create a sample schema for testing."""
    return SchemaMetadata(
        models={
            "Customer": ModelMetadata(
                name="Customer",
                table_name="customers",
                fields={
                    "id": FieldMetadata(
                        name="id",
                        field_type=FieldType.INTEGER,
                        nullable=False,
                    ),
                    "name": FieldMetadata(
                        name="name",
                        field_type=FieldType.STRING,
                        nullable=False,
                    ),
                    "email": FieldMetadata(
                        name="email",
                        field_type=FieldType.STRING,
                        nullable=True,
                        description="Customer email address",
                    ),
                    "password_hash": FieldMetadata(
                        name="password_hash",
                        field_type=FieldType.STRING,
                        nullable=False,
                    ),
                    "created_at": FieldMetadata(
                        name="created_at",
                        field_type=FieldType.DATETIME,
                        nullable=False,
                    ),
                },
                relations={},
            ),
            "Order": ModelMetadata(
                name="Order",
                table_name="orders",
                fields={
                    "id": FieldMetadata(
                        name="id",
                        field_type=FieldType.INTEGER,
                        nullable=False,
                    ),
                    "customer_id": FieldMetadata(
                        name="customer_id",
                        field_type=FieldType.INTEGER,
                        nullable=False,
                    ),
                    "total": FieldMetadata(
                        name="total",
                        field_type=FieldType.FLOAT,
                        nullable=False,
                    ),
                    "status": FieldMetadata(
                        name="status",
                        field_type=FieldType.STRING,
                        nullable=False,
                    ),
                },
                relations={},
            ),
        },
    )


@pytest.fixture
def sample_policy() -> Policy:
    """Create a sample policy for testing."""
    return Policy(
        models={
            "Customer": ModelPolicy(
                allowed=True,
                readable=True,
                writable=False,
                fields={
                    "password_hash": FieldPolicy(action=FieldAction.DENY),
                },
            ),
            "Order": ModelPolicy(
                allowed=True,
                readable=True,
                writable=True,
                write_policy=WritePolicy(
                    enabled=True,
                    allow_create=True,
                    allow_update=True,
                    allow_delete=True,
                    readonly_fields=["id", "created_at"],
                ),
            ),
        },
    )


class TestViewCodeGenerator:
    """Tests for ViewCodeGenerator."""

    def test_generates_view_file(self, sample_schema: SchemaMetadata, sample_policy: Policy):
        """Test that view file is generated."""
        generator = ViewCodeGenerator(sample_schema, sample_policy)
        result = generator.generate()

        assert len(result.files) == 1
        assert result.files[0].path == "views.py"
        assert result.files[0].module_name == "views"

    def test_generates_view_classes(self, sample_schema: SchemaMetadata, sample_policy: Policy):
        """Test that view classes are generated for allowed models."""
        generator = ViewCodeGenerator(sample_schema, sample_policy)
        result = generator.generate()

        content = result.files[0].content

        # Should have view classes for both models
        assert "class CustomerView(BaseView):" in content
        assert "class OrderView(BaseView):" in content

    def test_excludes_denied_fields(self, sample_schema: SchemaMetadata, sample_policy: Policy):
        """Test that denied fields are not included."""
        generator = ViewCodeGenerator(sample_schema, sample_policy)
        result = generator.generate()

        content = result.files[0].content

        # password_hash should be excluded
        assert "password_hash" not in content

        # Other fields should be present
        assert "id: int" in content
        assert "name: str" in content
        assert "email: str | None" in content

    def test_generates_create_views(self, sample_schema: SchemaMetadata, sample_policy: Policy):
        """Test that create views are generated for writable models."""
        generator = ViewCodeGenerator(sample_schema, sample_policy)
        result = generator.generate()

        content = result.files[0].content

        # Order is writable, should have create view
        assert "class OrderCreate(BaseModel):" in content

        # Customer is not writable, should not have create view
        assert "class CustomerCreate" not in content

    def test_generates_update_views(self, sample_schema: SchemaMetadata, sample_policy: Policy):
        """Test that update views are generated for writable models."""
        generator = ViewCodeGenerator(sample_schema, sample_policy)
        result = generator.generate()

        content = result.files[0].content

        # Order is writable, should have update view
        assert "class OrderUpdate(BaseModel):" in content

    def test_includes_field_descriptions(self, sample_schema: SchemaMetadata, sample_policy: Policy):
        """Test that field descriptions are included."""
        generator = ViewCodeGenerator(sample_schema, sample_policy)
        result = generator.generate()

        content = result.files[0].content

        # Email has a description
        assert 'description="Customer email address"' in content

    def test_handles_nullable_fields(self, sample_schema: SchemaMetadata, sample_policy: Policy):
        """Test that nullable fields have correct type."""
        generator = ViewCodeGenerator(sample_schema, sample_policy)
        result = generator.generate()

        content = result.files[0].content

        # email is nullable
        assert "email: str | None" in content

        # name is not nullable
        assert "name: str" in content
        # Make sure it's not optional
        lines = content.split("\n")
        name_lines = [l for l in lines if "name:" in l and "model" not in l.lower()]
        for line in name_lines:
            if "name: str" in line:
                assert "None" not in line

    def test_custom_module_name(self, sample_schema: SchemaMetadata, sample_policy: Policy):
        """Test custom module name."""
        generator = ViewCodeGenerator(
            sample_schema, sample_policy, module_name="my_views"
        )
        result = generator.generate()

        assert result.files[0].path == "my_views.py"
        assert result.files[0].module_name == "my_views"


class TestDomainToolGenerator:
    """Tests for DomainToolGenerator."""

    def test_generates_tool_file(self, sample_schema: SchemaMetadata, sample_policy: Policy):
        """Test that tool file is generated."""
        generator = DomainToolGenerator(sample_schema, sample_policy)
        result = generator.generate()

        assert len(result.files) == 1
        assert result.files[0].path == "domain_tools.py"

    def test_generates_input_schemas(self, sample_schema: SchemaMetadata, sample_policy: Policy):
        """Test that input schemas are generated."""
        generator = DomainToolGenerator(sample_schema, sample_policy)
        result = generator.generate()

        content = result.files[0].content

        # Should have input schemas for each model
        assert "class GetCustomerInput(BaseModel):" in content
        assert "class ListCustomerInput(BaseModel):" in content
        assert "class GetOrderInput(BaseModel):" in content
        assert "class ListOrderInput(BaseModel):" in content

    def test_generates_tool_classes(self, sample_schema: SchemaMetadata, sample_policy: Policy):
        """Test that tool classes are generated."""
        generator = DomainToolGenerator(sample_schema, sample_policy)
        result = generator.generate()

        content = result.files[0].content

        assert "class CustomerTools:" in content
        assert "class OrderTools:" in content

    def test_generates_get_method(self, sample_schema: SchemaMetadata, sample_policy: Policy):
        """Test that get methods are generated."""
        generator = DomainToolGenerator(sample_schema, sample_policy)
        result = generator.generate()

        content = result.files[0].content

        assert "async def get_customer(" in content
        assert "async def get_order(" in content

    def test_generates_list_method(self, sample_schema: SchemaMetadata, sample_policy: Policy):
        """Test that list methods are generated."""
        generator = DomainToolGenerator(sample_schema, sample_policy)
        result = generator.generate()

        content = result.files[0].content

        assert "async def list_customers(" in content
        assert "async def list_orders(" in content

    def test_generates_mutation_methods_for_writable(
        self, sample_schema: SchemaMetadata, sample_policy: Policy
    ):
        """Test that mutation methods are generated for writable models."""
        generator = DomainToolGenerator(sample_schema, sample_policy)
        result = generator.generate()

        content = result.files[0].content

        # Order is writable
        assert "async def create_order(" in content
        assert "async def update_order(" in content
        assert "async def delete_order(" in content

        # Customer is not writable
        assert "async def create_customer(" not in content
        assert "async def update_customer(" not in content

    def test_imports_views(self, sample_schema: SchemaMetadata, sample_policy: Policy):
        """Test that views are imported."""
        generator = DomainToolGenerator(sample_schema, sample_policy)
        result = generator.generate()

        content = result.files[0].content

        assert "from views import CustomerView, OrderView" in content

    def test_snake_case_conversion(self, sample_schema: SchemaMetadata, sample_policy: Policy):
        """Test that method names use snake_case."""
        generator = DomainToolGenerator(sample_schema, sample_policy)

        assert generator._to_snake_case("Customer") == "customer"
        assert generator._to_snake_case("OrderItem") == "order_item"
        assert generator._to_snake_case("APIKey") == "a_p_i_key"  # Edge case
