"""Test the contents of django_utils/graphql/django_connection.py"""
from inspect import cleandoc
from unittest import mock

from django.db import models
from django.test import SimpleTestCase
from graphene.relay import Node
from graphql_relay.node.node import to_global_id

from django_utils.graphql import django_connection


class TestConvertFieldLookup(SimpleTestCase):
    """Test that DEDjangoConnectionField.convert_field_lookup() works."""

    @staticmethod
    def convert_field_lookup(field_lookup: str) -> str:
        """Convenient function to shorten the function reference."""
        return django_connection.DEDjangoConnectionField.convert_field_lookup(
            field_lookup
        )

    def test_simple_lookups(self):
        """Test that the function can handle simple lookups."""
        test_cases = [
            ("reportName_Icontains", "report_name__icontains"),
            ("prefab", "prefab"),
        ]

        for input_str, expected_output_str in test_cases:
            with self.subTest(input=input_str, expected_output=expected_output_str):
                self.assertEqual(
                    self.convert_field_lookup(input_str), expected_output_str
                )

    def test_related_lookups(self):
        """Test that the function can handle lookups that traverse relationships."""
        test_cases = [
            ("partner_Name_Icontains", "partner__name__icontains"),
            ("partner_Name", "partner__name"),
            ("partner_OutreachTags", "partner__outreach_tags"),
        ]

        for input_str, expected_output_str in test_cases:
            with self.subTest(input=input_str, expected_output=expected_output_str):
                self.assertEqual(
                    self.convert_field_lookup(input_str), expected_output_str
                )


class TestDEDjangoObjectType(SimpleTestCase):
    """Test the DEDjangoObjectType class."""

    def test_description_model_docstring(self):
        """
        Test that if `description` is not provided, the object will get it from the
        model docstring.
        """

        class SampleModel(models.Model):
            """
            SampleModel's docstring.

            Here's some extra information on a new line!
            """

        class SampleModelObjectType(django_connection.DEDjangoObjectType):
            class Meta:
                model = SampleModel

        self.assertEqual(
            SampleModelObjectType._meta.description, cleandoc(SampleModel.__doc__)
        )

    def test_description_standard(self):
        """
        Test that you can still specify the object description with a docstring or property.
        """

        class SampleModel2(models.Model):
            """SampleModel2's docstring"""

        class SampleModelObjectTypeDocstring(django_connection.DEDjangoObjectType):
            """The SampleModelObjectTypeDocstring docstring."""

            class Meta:
                model = SampleModel2

        self.assertEqual(
            SampleModelObjectTypeDocstring._meta.description,
            cleandoc(SampleModelObjectTypeDocstring.__doc__),
        )

        class SampleModelObjectTypeProperty(django_connection.DEDjangoObjectType):
            class Meta:
                model = SampleModel2
                description = "The SampleModelObjectTypeProperty property."

        self.assertEqual(
            SampleModelObjectTypeProperty._meta.description,
            SampleModelObjectTypeProperty._meta.description,
        )


# These classes are out here to simplify the tests because of their
# dynamic class modification.
class SimpleModel(models.Model):
    """A simple model for testing"""


@django_connection.add_resolve_reference
class SimpleModelNode(django_connection.DjangoObjectType):
    class Meta:
        model = SimpleModel
        interfaces = (Node,)


class TestAddResolveReference(SimpleTestCase):
    """Test the `add_resolve_reference` decorator."""

    def test_decorator(self):
        """Test that the __resolve_reference is added to the class."""
        node = SimpleModelNode()
        method_name = "_{}__resolve_reference".format(SimpleModelNode.__name__)
        self.assertTrue(
            hasattr(node, method_name),
            "The class did not have '{}' added to it.".format(method_name),
        )

    def test_resolve_method(self):
        """
        Test that `_resolve_reference` calls the get_node method on a DjangoObjectType.
        """
        # Make a model to return
        model = mock.MagicMock(spec=SimpleModel)
        model.id = 1

        # Make a SimpleModelNode with a global ID
        node = SimpleModelNode(id=to_global_id(SimpleModelNode.__name__, model.id))
        # and define its `get_node` so it doesn't check the DB
        node.get_node = mock.MagicMock(return_value=model)

        # Run the function with the inputs
        info = mock.MagicMock()
        output = django_connection._resolve_reference(node, info)

        # Test the result, and how get_node was called
        self.assertEqual(output, model)
        node.get_node.assert_called_with(info, model.id)
