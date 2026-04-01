"""
Property-based tests for DSL and input validation using Hypothesis.

These tests verify that the DSL models and validation functions
behave correctly across a wide range of inputs.
"""

from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.strategies import booleans, dictionaries, integers, lists, none

from ormai.core.dsl import (
    AggregateRequest,
    BulkUpdateRequest,
    CreateRequest,
    DeleteRequest,
    FilterClause,
    FilterOp,
    GetRequest,
    IncludeClause,
    OrderClause,
    OrderDirection,
    QueryRequest,
    UpdateRequest,
)
from ormai.store.sanitize import SENSITIVE_PATTERNS, sanitize_inputs

# === Strategy Definitions ===

@st.composite
def filter_ops_strategy(draw):
    """Generate valid filter operations."""
    return draw(st.sampled_from(list(FilterOp)))


@st.composite
def order_directions_strategy(draw):
    """Generate valid order directions."""
    return draw(st.sampled_from(list(OrderDirection)))


@st.composite
def filter_clause_strategy(draw):
    """Generate valid filter clauses with valid field names."""
    return FilterClause(
        field=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=['Ll', 'Lu', 'Nd'],
            whitelist_characters=['_'],
        ))),
        op=draw(filter_ops_strategy()),
        value=draw(st.one_of(st.text(), integers(), st.floats(), booleans())),
    )


@st.composite
def order_clause_strategy(draw):
    """Generate valid order clauses with valid field names."""
    return OrderClause(
        field=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=['Ll', 'Lu', 'Nd'],
            whitelist_characters=['_'],
        ))),
        direction=draw(order_directions_strategy()),
    )


@st.composite
def include_clause_strategy(draw):
    """Generate valid include clauses with valid relation names."""
    return IncludeClause(
        relation=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=['Ll', 'Lu', 'Nd'],
            whitelist_characters=['_'],
        ))),
        select=draw(lists(st.text(min_size=1, max_size=50), max_size=5)),
        where=draw(lists(filter_clause_strategy(), max_size=3)),
        depth=draw(integers(min_value=1, max_value=5)),
    )


@st.composite
def query_request_strategy(draw):
    """Generate valid QueryRequest objects."""
    return QueryRequest(
        model=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=['Ll', 'Lu', 'Nd'],
        ))),
        select=draw(lists(st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=['Ll', 'Lu', 'Nd'],
            whitelist_characters=['_'],
        )), max_size=10)),
        where=draw(lists(filter_clause_strategy(), max_size=5)),
        order_by=draw(lists(order_clause_strategy(), max_size=3)),
        include=draw(lists(include_clause_strategy(), max_size=2)),
        # take has default=25 and ge=1 constraint, must be int
        take=draw(integers(min_value=1, max_value=100)),
        cursor=draw(st.text() | none()),
    )


@st.composite
def get_request_strategy(draw):
    """Generate valid GetRequest objects."""
    return GetRequest(
        model=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=['Ll', 'Lu', 'Nd'],
        ))),
        id=draw(integers(min_value=1)),
        select=draw(lists(st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=['Ll', 'Lu', 'Nd'],
            whitelist_characters=['_'],
        )), max_size=10)),
    )


@st.composite
def aggregate_request_strategy(draw):
    """Generate valid AggregateRequest objects."""
    return AggregateRequest(
        model=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=['Ll', 'Lu', 'Nd'],
        ))),
        operation=draw(st.sampled_from(["count", "sum", "avg", "min", "max"])),
        field=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=['Ll', 'Lu', 'Nd'],
            whitelist_characters=['_'],
        )) | none()),
    )


@st.composite
def create_request_strategy(draw):
    """Generate valid CreateRequest objects."""
    return CreateRequest(
        model=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=['Ll', 'Lu', 'Nd'],
        ))),
        data=draw(dictionaries(
            st.text(min_size=1, max_size=50, alphabet=st.characters(
                whitelist_categories=['Ll', 'Lu', 'Nd'],
                whitelist_characters=['_'],
            )),
            st.one_of(st.text(), integers(), st.floats(), booleans()),
            max_size=10,
        )),
    )


@st.composite
def update_request_strategy(draw):
    """Generate valid UpdateRequest objects."""
    return UpdateRequest(
        model=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=['Ll', 'Lu', 'Nd'],
        ))),
        id=draw(integers(min_value=1)),
        data=draw(dictionaries(
            st.text(min_size=1, max_size=50, alphabet=st.characters(
                whitelist_categories=['Ll', 'Lu', 'Nd'],
                whitelist_characters=['_'],
            )),
            st.one_of(st.text(), integers(), st.floats(), booleans()),
            max_size=10,
        )),
    )


@st.composite
def delete_request_strategy(draw):
    """Generate valid DeleteRequest objects."""
    return DeleteRequest(
        model=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=['Ll', 'Lu', 'Nd'],
        ))),
        id=draw(integers(min_value=1)),
    )


@st.composite
def bulk_update_request_strategy(draw):
    """Generate valid BulkUpdateRequest objects (with at least 1 id)."""
    return BulkUpdateRequest(
        model=draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=['Ll', 'Lu', 'Nd'],
        ))),
        ids=draw(lists(integers(min_value=1), min_size=1, max_size=20)),
        data=draw(dictionaries(
            st.text(min_size=1, max_size=50, alphabet=st.characters(
                whitelist_categories=['Ll', 'Lu', 'Nd'],
                whitelist_characters=['_'],
            )),
            st.one_of(st.text(), integers(), st.floats(), booleans()),
            max_size=10,
        )),
    )


# === DSL Model Tests ===

class TestQueryRequestProperties:
    """Property-based tests for QueryRequest."""

    @given(query_request_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_query_request_has_all_fields(self, request):
        """Test that generated QueryRequest has all expected fields."""
        assert hasattr(request, 'model')
        assert hasattr(request, 'select')
        assert hasattr(request, 'where')
        assert hasattr(request, 'order_by')
        assert hasattr(request, 'include')
        assert hasattr(request, 'take')
        assert hasattr(request, 'cursor')

    @given(query_request_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_query_request_model_is_string(self, request):
        """Test that model is always a non-empty string."""
        assert isinstance(request.model, str)
        assert len(request.model) > 0

    @given(query_request_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_query_request_select_is_list(self, request):
        """Test that select is always a list."""
        assert isinstance(request.select, list)

    @given(query_request_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_query_request_where_is_list(self, request):
        """Test that where is always a list."""
        assert isinstance(request.where, list)


class TestGetRequestProperties:
    """Property-based tests for GetRequest."""

    @given(get_request_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_get_request_has_all_fields(self, request):
        """Test that generated GetRequest has all expected fields."""
        assert hasattr(request, 'model')
        assert hasattr(request, 'id')
        assert hasattr(request, 'select')

    @given(get_request_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_get_request_id_is_positive(self, request):
        """Test that id is always a positive integer."""
        assert isinstance(request.id, int)
        assert request.id > 0


class TestFilterClauseProperties:
    """Property-based tests for FilterClause."""

    @given(filter_clause_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_filter_clause_has_all_fields(self, clause):
        """Test that generated FilterClause has all expected fields."""
        assert hasattr(clause, 'field')
        assert hasattr(clause, 'op')
        assert hasattr(clause, 'value')

    @given(filter_clause_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_filter_clause_field_is_string(self, clause):
        """Test that field is always a non-empty string."""
        assert isinstance(clause.field, str)
        assert len(clause.field) > 0

    @given(filter_clause_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_filter_clause_op_is_valid(self, clause):
        """Test that op is a valid FilterOp."""
        assert isinstance(clause.op, FilterOp)


class TestOrderClauseProperties:
    """Property-based tests for OrderClause."""

    @given(order_clause_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_order_clause_has_all_fields(self, clause):
        """Test that generated OrderClause has all expected fields."""
        assert hasattr(clause, 'field')
        assert hasattr(clause, 'direction')

    @given(order_clause_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_order_clause_direction_is_valid(self, clause):
        """Test that direction is a valid OrderDirection."""
        assert isinstance(clause.direction, OrderDirection)


# === Sanitization Tests ===

class TestSanitizeInputsProperties:
    """Property-based tests for sanitize_inputs function."""

    @given(dictionaries(
        st.text(min_size=0, max_size=50),
        st.one_of(st.text(), integers(), booleans()),
        max_size=20,
    ))
    @settings(max_examples=50, deadline=5000)
    def test_sanitize_inputs_returns_dict(self, data):
        """Test that sanitize_inputs always returns a dict."""
        result = sanitize_inputs(data)
        assert isinstance(result, dict)
        assert len(result) == len(data)

    @given(dictionaries(
        st.text(min_size=0, max_size=50),
        st.one_of(st.text(), integers(), booleans()),
        max_size=20,
    ))
    @settings(max_examples=50, deadline=5000)
    def test_sanitize_inputs_preserves_keys(self, data):
        """Test that sanitize_inputs preserves keys."""
        result = sanitize_inputs(data)
        assert set(result.keys()) == set(data.keys())

    @given(st.text(min_size=0, max_size=100))
    @settings(max_examples=50, deadline=5000)
    def test_sanitize_inputs_empty_dict(self, _text_data):
        """Test that sanitize_inputs handles empty dict."""
        result = sanitize_inputs({})
        assert result == {}

    @given(dictionaries(
        st.text(min_size=1, max_size=50),
        st.text(min_size=0, max_size=100),
        max_size=20,
    ))
    @settings(max_examples=50, deadline=5000)
    def test_sanitize_inputs_redacts_sensitive_fields(self, _data):
        """Test that sensitive fields are redacted."""
        sensitive_data = {
            "password": "secret123",
            "token": "abc123",
            "api_key": "key123",
        }
        result = sanitize_inputs(sensitive_data)
        assert result["password"] == "[REDACTED]"
        assert result["token"] == "[REDACTED]"
        assert result["api_key"] == "[REDACTED]"


class TestSensitivePatternProperties:
    """Property-based tests for sensitive pattern detection."""

    @given(st.text(min_size=0, max_size=100))
    @settings(max_examples=50, deadline=5000)
    def test_sensitive_pattern_matches_password_variants(self, _text):
        """Test that password variants are detected."""
        password_variants = ["password", "Password", "PASSWORD", "user_password"]
        for variant in password_variants:
            assert SENSITIVE_PATTERNS.search(variant) is not None

    @given(st.text(min_size=0, max_size=100))
    @settings(max_examples=50, deadline=5000)
    def test_sensitive_pattern_matches_token_variants(self, _text):
        """Test that token variants are detected."""
        token_variants = ["token", "Token", "access_token", "refresh_token"]
        for variant in token_variants:
            assert SENSITIVE_PATTERNS.search(variant) is not None

    @given(st.text(min_size=0, max_size=100))
    @settings(max_examples=50, deadline=5000)
    def test_sensitive_pattern_matches_api_key_variants(self, _text):
        """Test that API key variants are detected."""
        api_key_variants = ["api_key", "apikey", "api_secret", "client_secret"]
        for variant in api_key_variants:
            assert SENSITIVE_PATTERNS.search(variant) is not None

    @given(st.text(min_size=0, max_size=100))
    @settings(max_examples=50, deadline=5000)
    def test_sensitive_pattern_is_case_insensitive(self, _text):
        """Test that pattern matching is case insensitive."""
        lower = "password"
        upper = "PASSWORD"
        mixed = "PaSsWoRd"
        assert SENSITIVE_PATTERNS.search(lower) is not None
        assert SENSITIVE_PATTERNS.search(upper) is not None
        assert SENSITIVE_PATTERNS.search(mixed) is not None

    @given(st.text(min_size=0, max_size=100))
    @settings(max_examples=50, deadline=5000)
    def test_sensitive_pattern_non_sensitive_not_detected(self, _text):
        """Test that non-sensitive fields are not detected."""
        non_sensitive = ["name", "email", "address", "phone", "age", "created_at"]
        for field in non_sensitive:
            assert SENSITIVE_PATTERNS.search(field) is None


# === Mutation Request Tests ===

class TestCreateRequestProperties:
    """Property-based tests for CreateRequest."""

    @given(create_request_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_create_request_has_all_fields(self, request):
        """Test that generated CreateRequest has all expected fields."""
        assert hasattr(request, 'model')
        assert hasattr(request, 'data')

    @given(create_request_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_create_request_model_is_string(self, request):
        """Test that model is always a non-empty string."""
        assert isinstance(request.model, str)
        assert len(request.model) > 0

    @given(create_request_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_create_request_data_is_dict(self, request):
        """Test that data is always a dict."""
        assert isinstance(request.data, dict)


class TestUpdateRequestProperties:
    """Property-based tests for UpdateRequest."""

    @given(update_request_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_update_request_has_all_fields(self, request):
        """Test that generated UpdateRequest has all expected fields."""
        assert hasattr(request, 'model')
        assert hasattr(request, 'id')
        assert hasattr(request, 'data')

    @given(update_request_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_update_request_id_is_positive(self, request):
        """Test that id is always a positive integer."""
        assert isinstance(request.id, int)
        assert request.id > 0


class TestBulkUpdateRequestProperties:
    """Property-based tests for BulkUpdateRequest."""

    @given(bulk_update_request_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_bulk_update_request_has_all_fields(self, request):
        """Test that generated BulkUpdateRequest has all expected fields."""
        assert hasattr(request, 'model')
        assert hasattr(request, 'ids')
        assert hasattr(request, 'data')

    @given(bulk_update_request_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_bulk_update_request_ids_are_positive(self, request):
        """Test that all ids are positive integers."""
        for id in request.ids:
            assert isinstance(id, int)
            assert id > 0

    @given(bulk_update_request_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_bulk_update_request_has_at_least_one_id(self, request):
        """Test that bulk update has at least one id."""
        assert len(request.ids) >= 1


# === Nested Data Tests ===

class TestNestedDataSanitization:
    """Property-based tests for nested data sanitization."""

    @given(dictionaries(
        st.text(min_size=1, max_size=30),
        st.one_of(
            st.text(),
            integers(),
            dictionaries(st.text(), st.text(), max_size=5),
            lists(st.text(), max_size=5),
        ),
        max_size=10,
    ))
    @settings(max_examples=50, deadline=5000)
    def test_sanitize_nested_dicts(self, data):
        """Test that nested dicts are sanitized."""
        result = sanitize_inputs(data)
        assert isinstance(result, dict)
        assert len(result) == len(data)

    @given(lists(
        dictionaries(st.text(), st.text() | integers(), max_size=5),
        max_size=10,
    ))
    @settings(max_examples=50, deadline=5000)
    def test_sanitize_list_of_dicts(self, data):
        """Test that list of dicts is sanitized."""
        wrapper = {"items": data}
        result = sanitize_inputs(wrapper)
        assert isinstance(result, dict)
        assert isinstance(result["items"], list)


# === Boundary Value Tests ===

class TestBoundaryValueTests:
    """Tests for boundary values in DSL models."""

    @given(integers(min_value=1, max_value=100))
    @settings(max_examples=20, deadline=5000)
    def test_query_take_boundary(self, take_value):
        """Test that query take values in valid range work."""
        request = QueryRequest(
            model="User",
            select=["id"],
            take=take_value,
        )
        assert request.take == take_value

    @given(integers(min_value=1, max_value=100))
    @settings(max_examples=20, deadline=5000)
    def test_bulk_update_ids_boundary(self, count):
        """Test bulk update with various id counts."""
        ids = list(range(1, count + 1))
        request = BulkUpdateRequest(
            model="User",
            ids=ids,
            data={"status": "active"},
        )
        assert len(request.ids) == len(ids)

    @given(lists(st.text(max_size=50), min_size=0, max_size=50))
    @settings(max_examples=20, deadline=5000)
    def test_query_select_list_boundary(self, select_list):
        """Test query select with various list sizes."""
        request = QueryRequest(
            model="User",
            select=select_list,
        )
        assert len(request.select) == len(select_list)
