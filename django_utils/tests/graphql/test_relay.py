"""Test the code from `django_utils/graphql/relay.py`."""

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from graphql_relay.node.node import to_global_id

from django_utils.graphql import errors, relay


class TestIdOrRaise(SimpleTestCase):
    """Test the behavior of the `id_or_raise()` function."""

    def test_success(self):
        """Test that the correct value is returned."""
        input_id = 69
        global_id = to_global_id("Model", input_id)

        self.assertEqual(relay.id_or_raise(global_id, None), input_id)

    def test_failure(self):
        """Test the exception raised on failure."""
        field_name = "field_a"
        with self.assertRaises(ValidationError) as cm:
            relay.id_or_raise("abc123", field_name)

        self.assertIn(field_name, cm.exception.error_dict)
        inner_exception = cm.exception.error_dict[field_name][0]

        self.assertEqual(inner_exception.code, errors.ERROR_VALIDATION)
