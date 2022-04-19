import typing
from unittest import mock

from django.test import SimpleTestCase
from graphql_relay.node.node import to_global_id

from django_utils.graphql.errors import GraphQLError
from django_utils.graphql.filters import (
    ErrorHandlingGlobalIDField,
    ErrorHandlingGlobalIDMultipleChoiceField,
    ErrorHandlingMultipleChoiceField,
    GlobalIDFilterWithErrors,
    GlobalIDMultipleChoiceFilterWithErrors,
    MultipleChoiceFilterWithErrors,
)


class TestErrorHandlingFilter(SimpleTestCase):
    """
    This test checks that the various error-handling filters can be run successfully.
    (any Filter field that uses a form which extends
    `.graphql.filters.ErrorHandlingFilterField`)

    For full coverage, these filter fields should as be integration tested on the GraphQL
    queries where they are used.
    """

    def test_global_id_filter(self):
        queryset_mock = mock.MagicMock()
        actual_id = 4
        test_value = to_global_id("SomeTypeName", actual_id)
        field_name = "field_name"

        filter_set = GlobalIDFilterWithErrors(field_name=field_name)
        filter_set.filter(queryset_mock, test_value)
        queryset_mock.filter.assert_called_with(field_name__exact=str(actual_id))

    def test_multiple_choice_filter(self):
        queryset_mock = mock.MagicMock()
        choices = (("one", "one"), ("two", "two"), ("three", "three"))
        field_name = "field_name"

        filter_set = MultipleChoiceFilterWithErrors(
            field_name=field_name,
            choices=choices,
        )
        filter_args = [choices[0][0], choices[1][0]]
        filter_set.filter(queryset_mock, filter_args)
        self._assert_mock_queryset_called_with(filter_args, queryset_mock.filter)

    def test_global_id_multiple_choice_filter(self):
        queryset_mock = mock.MagicMock()
        test_id_one = "4"
        global_id_one = to_global_id("SomeTypeName", test_id_one)
        test_id_two = "5"
        global_id_two = to_global_id("SomeTypeName", test_id_two)
        filter_input = [global_id_one, global_id_two]
        expected_results = [test_id_one, test_id_two]
        field_name = "field_name"

        filter_set = GlobalIDMultipleChoiceFilterWithErrors(field_name=field_name)
        filter_set.filter(queryset_mock, filter_input)
        self._assert_mock_queryset_called_with(expected_results, queryset_mock.filter)

    def _assert_mock_queryset_called_with(
        self, expected_values: typing.List[str], mock_call: mock.MagicMock
    ):
        """
        Extracts some of the processing logic required to assert that querysets (mocked
        with a MagicMock) have `filter` called with the correct query-args.
        """
        call_q = mock_call.call_args[0][0]
        queried_values = [child[1] for child in call_q.children]
        self.assertCountEqual(expected_values, queried_values)


class TestErrorHandlingFormField(SimpleTestCase):
    """
    Tests the `clean` method for all extensions of the `ErrorHandlingFilterField` django
    field. Checks that the clean method raises a GraphQLError when invalid data is
    passed, and checks that it returns the correct values when valid data is passed.
    """

    def test_global_id_field_clean_no_errors(self):
        test_cases = [
            {
                "test name": "valid ID",
                "field required": False,
                "value": "Q29udmVyc2F0aW9uVXNlck5vZGU6MQ==",
                "expected": "Q29udmVyc2F0aW9uVXNlck5vZGU6MQ==",
            },
            {
                "test name": "valid ID (required)",
                "field required": True,
                "value": "Q29udmVyc2F0aW9uVXNlck5vZGU6MQ==",
                "expected": "Q29udmVyc2F0aW9uVXNlck5vZGU6MQ==",
            },
            {
                "test name": "emptystring",
                "field required": False,
                "value": "",
                "expected": None,
            },
            {
                "test name": "Nonetype",
                "field required": False,
                "value": None,
                "expected": None,
            },
        ]

        for case in test_cases:
            value = case["value"]
            expected_value = case["expected"]
            with self.subTest(case.get("test name")):
                field = ErrorHandlingGlobalIDField(required=case["field required"])
                result = field.clean(value)
                self.assertEqual(expected_value, result)

    def test_global_id_field_clean_with_errors(self):
        test_cases = [
            {
                "test name": "emptystring, when field required",
                "field required": True,
                "value": "",
                "expected": "Invalid Relay ID",
            },
            {
                "test name": "Nonetype, when field required",
                "field required": True,
                "value": None,
                "expected": "Invalid Relay ID",
            },
            {
                "test name": "garbage text",
                "field required": False,
                "value": "asdfjoasd",
            },
            {
                "test name": "non-ID base-64",
                "field required": False,
                "value": "bXkgY3JlZGl0LWNhcmQgbnVtYmVy",
            },
            {
                "test name": "non-string passed",
                "field required": False,
                "value": 1,
            },
        ]

        for case in test_cases:
            value = case["value"]
            with self.subTest(case.get("test name")):
                field = ErrorHandlingGlobalIDField(required=case["field required"])
                with self.assertRaises(GraphQLError):
                    field.clean(value)

    def test_global_id_multiple_choice_field_clean_no_errors(self):
        valid_global_id = to_global_id("Typename", "1")
        test_cases = [
            {
                "test name": "valid ID",
                "field required": False,
                "value": [valid_global_id],
                "expected": [valid_global_id],
            },
            {
                "test name": "valid ID (required)",
                "field required": True,
                "value": [valid_global_id],
                "expected": [valid_global_id],
            },
            {
                "test name": "emptystring",
                "field required": False,
                "value": "",
                "expected": [],
            },
            {
                "test name": "Nonetype",
                "field required": False,
                "value": None,
                "expected": [],
            },
        ]

        for case in test_cases:
            value = case["value"]
            expected_value = case["expected"]
            with self.subTest(case.get("test name")):
                field = ErrorHandlingGlobalIDMultipleChoiceField(
                    required=case["field required"]
                )
                result = field.clean(value)
                self.assertEqual(expected_value, result)

    def test_global_id_multiple_choice_field_clean_with_errors(self):
        valid_global_id = to_global_id("Typename", "1")
        test_cases = [
            {
                "test name": "emptystring, when field required",
                "field required": False,
                "value": [""],
                "expected": "Invalid Relay ID",
            },
            {
                "test name": "Nonetype, for id",
                "field required": False,
                "value": [None],
                "expected": "Invalid Relay ID",
            },
            {
                "test name": "Nonetype when field required",
                "field required": True,
                "value": None,
                "expected": "Invalid Relay ID",
            },
            {
                "test name": "Emptystring when field required",
                "field required": True,
                "value": "",
                "expected": "Invalid Relay ID",
            },
            {
                "test name": "garbage text",
                "field required": False,
                "value": "asdfjoasd",
            },
            {
                "test name": "garbage text for an ID",
                "field required": False,
                "value": [valid_global_id, "asdfjoasd"],
            },
            {
                "test name": "non-ID base-64",
                "field required": False,
                "value": ["bXkgY3JlZGl0LWNhcmQgbnVtYmVy"],
            },
            {
                "test name": "non-string passed",
                "field required": False,
                "value": 1,
            },
            {
                "test name": "non-string passed as ID",
                "field required": False,
                "value": [1],
            },
        ]

        for case in test_cases:
            value = case["value"]
            with self.subTest(case.get("test name")):
                field = ErrorHandlingGlobalIDMultipleChoiceField(
                    required=case["field required"]
                )
                with self.assertRaises(GraphQLError):
                    field.clean(value)

    def test_multiple_choice_field_clean_no_errors(self):
        choices = (
            ("one", "one"),
            ("two", "two"),
        )
        test_cases = [
            {
                "test name": "valid choice",
                "field required": False,
                "value": [choices[0][0]],
                "expected": [choices[0][0]],
            },
            {
                "test name": "multiple choices",
                "field required": False,
                "value": [choices[0][0], choices[1][0]],
                "expected": [choices[0][0], choices[1][0]],
            },
            {
                "test name": "valid choice (required)",
                "field required": True,
                "value": [choices[0][0]],
                "expected": [choices[0][0]],
            },
            {
                "test name": "emptystring",
                "field required": False,
                "value": "",
                "expected": [],
            },
            {
                "test name": "Nonetype",
                "field required": False,
                "value": None,
                "expected": [],
            },
        ]

        for case in test_cases:
            value = case["value"]
            expected_value = case["expected"]
            with self.subTest(case.get("test name")):
                field = ErrorHandlingMultipleChoiceField(
                    required=case["field required"],
                    choices=choices,
                )
                result = field.clean(value)
                self.assertEqual(expected_value, result)

    def test_multiple_choice_field_clean_with_errors(self):
        choices = (
            ("one", "one"),
            ("two", "two"),
        )
        test_cases = [
            {
                "test name": "emptystring for choice",
                "field required": False,
                "value": [""],
                "expected": "Invalid Relay ID",
            },
            {
                "test name": "Nonetype, for choice",
                "field required": False,
                "value": [None],
                "expected": "Invalid Relay ID",
            },
            {
                "test name": "Nonetype when field required",
                "field required": True,
                "value": None,
                "expected": "Invalid Relay ID",
            },
            {
                "test name": "Emptystring when field required",
                "field required": True,
                "value": "",
                "expected": "Invalid Relay ID",
            },
            {
                "test name": "garbage text",
                "field required": False,
                "value": "asdfjoasd",
            },
            {
                "test name": "invalid choice",
                "field required": False,
                "value": [choices[0][0], "asdfjoasd"],
            },
            {
                "test name": "non-string passed",
                "field required": False,
                "value": 1,
            },
            {
                "test name": "non-string passed as choice",
                "field required": False,
                "value": [1],
            },
        ]

        for case in test_cases:
            value = case["value"]
            with self.subTest(case.get("test name")):
                field = ErrorHandlingMultipleChoiceField(
                    required=case["field required"],
                    choices=choices,
                )
                with self.assertRaises(GraphQLError):
                    field.clean(value)
