"""Test the contents of shared_library/graphql/errors.py"""
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.test import TestCase
from graphql import GraphQLError

from shared_library.graphql import errors


class TestError(TestCase):
    """Test the Error class"""

    def test_str(self):
        """Test that the __str__ method works correctly."""
        kwargs = {
            "field": "fieldA",
            "message": "Test error",
            "code": errors.ERROR_NOT_FOUND,
        }
        error = errors.Error(**kwargs)
        self.assertEqual(
            str(error),
            "Error(code: {code}, field: {field}, message: {message})".format(**kwargs),
        )

    def test_repr(self):
        """Test that the __repr__ method works correctly."""
        kwargs = {
            "field": "fieldA",
            "message": "Test error",
            "code": errors.ERROR_NOT_FOUND,
        }
        original_error = errors.Error(**kwargs)
        new_error = eval(repr(original_error), {"Error": errors.Error})
        self.assertEqual(original_error, new_error)

    def test_eq(self):
        """Test that the __eq__ method works correctly."""
        kwargs = {
            "field": "fieldA",
            "message": "test error",
            "code": errors.ERROR_NOT_FOUND,
        }
        error_a = errors.Error(**kwargs)
        error_b = errors.Error(**kwargs)
        self.assertEqual(error_a, error_b)


class MockedSource(object):
    def __init__(self, body=None):
        if not body:
            body = (
                "query{\n  node_a{\n    node_b(first:1){\n      edges{\n      }\n  }\n}"
            )
        self.body = body


class MockedGraphQLError(object):
    def __init__(self, error_type="generic"):
        if error_type == "generic":
            self.message = ""
        elif error_type == "located":
            self.original_error = ValueError("some internal error")
            self.path = ["node_a", "node_b"]
            self.source = MockedSource()


class TestFunctions(TestCase):
    """Test the stand-alone functions in errors.py"""

    def test_send_error_to_datadog_graphql(self):
        """Test that send_error_to_datadog works when provided a GraphQLError"""
        try:
            raise GraphQLError("Test GraphQL exception", path=["path", "to", "error"])
        except GraphQLError as error:
            # No exceptions should be thrown
            errors.send_error_to_datadog(error)

    def test_send_error_to_datadog_other(self):
        """Test that send_error_to_datadog works when provided a regular Exception"""
        try:
            raise Exception("Test Python exception")
        except Exception as error:
            # No exceptions should be thrown
            errors.send_error_to_datadog(error)

    def test_get_error_path_with_generic_exception(self):
        """Test that get_error_path works with a generic exception."""
        res = errors.get_error_path(Exception("basic exception"))
        self.assertEqual("", res)

    def test_get_error_path_with_located_error(self):
        """Test that get_error_path works with a GraphQL exception."""
        graphql_located_error = MockedGraphQLError(error_type="located")
        expected_path = "node_a.node_b"
        res = errors.get_error_path(graphql_located_error)
        self.assertEqual(expected_path, res)

    def test_get_error_type_with_generic_exception(self):
        """Test that get_error_type works with a generic exception."""
        res = errors.get_error_type(Exception("basic exception"))
        self.assertEqual("Exception", res)

    def test_get_error_type_with_located_error(self):
        """Test that get_error_type works with a GraphQL exception."""
        graphql_located_error = MockedGraphQLError(error_type="located")
        res = errors.get_error_type(graphql_located_error)
        self.assertEqual("MockedGraphQLError:ValueError", res)

    def test_get_request_body_from_located_error(self):
        """Test that get_request_body can get the request body from an error."""
        expected_request = "invalid request"
        graphql_located_error = MockedGraphQLError(error_type="located")
        source = MockedSource(body=expected_request)
        graphql_located_error.source = source
        res = errors.get_request_body(graphql_located_error)
        self.assertEqual(expected_request, res)

    def test_validation_error_to_graphql(self):
        """Test the behavior of `validation_error_to_graphql`."""
        error = ValidationError(
            {
                "name": [
                    ValidationError(
                        "Invalid value: %(value)s",
                        code="invalid",
                        params={"value": "john"},
                    )
                ],
                "title": [
                    ValidationError(
                        "Invalid value: %(value)s",
                        code="invalid",
                        params={"value": "programmer"},
                    )
                ],
            }
        )
        returned_errors = errors.validation_error_to_graphql(error)

        self.assertCountEqual(
            returned_errors,
            [
                errors.Error(
                    field="name",
                    message="Invalid value: john",
                    code=errors.ERROR_VALIDATION,
                ),
                errors.Error(
                    field="title",
                    message="Invalid value: programmer",
                    code=errors.ERROR_VALIDATION,
                ),
            ],
        )

    def test_integrity_error_to_graphql(self):
        """Test the behavior of `integrity_error_to_graphql`."""
        error = IntegrityError("Bad key")
        returned_errors = errors.integrity_error_to_graphql(error)

        self.assertCountEqual(
            returned_errors,
            [dict(code=errors.ERROR_INTEGRITY, message="Bad key", field="")],
        )

    def test_prefix_error_fields(self):
        """Test that `prefix_error_fields` behaves as expected."""
        error = ValidationError(
            {
                "name": [
                    ValidationError(
                        "Invalid value: %(value)s",
                        code="invalid",
                        params={"value": "john"},
                    )
                ],
                "title": [
                    ValidationError(
                        "Invalid value: %(value)s",
                        code="invalid",
                        params={"value": "programmer"},
                    )
                ],
            }
        )
        returned_error = errors.prefix_error_fields("abc.", error)

        self.assertEqual(
            returned_error.error_dict["abc.name"], error.error_dict["name"]
        )
        self.assertEqual(
            returned_error.error_dict["abc.title"], error.error_dict["title"]
        )

    def test_error_field_prefix(self):
        """
        Test that the error_field_prefix context manager prefixes fields in ValidationErrors.
        """
        with self.assertRaises(ValidationError) as cm:
            with errors.error_field_prefix("abc."):
                raise ValidationError(
                    {
                        "name": [
                            ValidationError(
                                "Invalid value: %(value)s",
                                code="invalid",
                                params={"value": "john"},
                            )
                        ]
                    }
                )

        self.assertIn("abc.name", cm.exception.error_dict)
