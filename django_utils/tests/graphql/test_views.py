"""Test the contents of django_utils/graphql/views.py"""
import logging
from unittest import mock

from django.test import SimpleTestCase
from graphql.error import GraphQLError, GraphQLLocatedError

from django_utils.graphql import errors, views


class TestDEGraphQLView(SimpleTestCase):
    """Test the behavior of DEGraphQLView."""

    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)

    def test_format_error_internal(self):
        """Test that generic internal errors are sanitized."""
        result = views.DEGraphQLView.format_error(Exception("secret"))

        self.assertEqual(result["code"], errors.ERROR_SERVER_FAILURE)
        self.assertEqual(result["message"], "Something went wrong.")

    def test_format_error_graphql(self):
        """Test that Graphql errors are formatted appropriately."""
        result = views.DEGraphQLView.format_error(GraphQLError("error"))

        self.assertEqual(result["message"], "error")

    @mock.patch.object(views.logger, "error")
    def test_format_error_graphql_located(self, mock_log: mock.MagicMock):
        """
        Test that GraphQLLocatedError errors are formatted appropriately.

        `self.assertLogs` was not used because in our settings files, logging is
        disabled when running tests at the Django app level. Testing with mock calls is
        less "correct", but it works in more cases.
        """
        message = "fiddlesticks"
        error = GraphQLLocatedError([], original_error=errors.GraphQLError(message))
        result = views.DEGraphQLView.format_error(error)

        mock_log.assert_called_once()
        self.assertEqual(result["code"], errors.ERROR_NOT_FOUND)
        self.assertEqual(result["message"], message)

    def test_format_error_path(self):
        """Test that paths are included by format_error."""
        error = Exception("error")
        error.path = ["a", "b", "c"]
        result = views.DEGraphQLView.format_error(error)
        self.assertEqual(result["path"], ".".join(error.path))

    @mock.patch("django_utils.graphql.views.send_error_to_datadog")
    def test_format_error_datadog(self, mock_send: mock.Mock):
        """Test that send_error_to_datadog is called with the original error."""
        error = GraphQLLocatedError([], original_error=Exception("error"))
        views.DEGraphQLView.format_error(error)
        mock_send.assert_called_with(error.original_error)

    @mock.patch.object(views.logger, "error")
    @mock.patch("django_utils.graphql.views.send_error_to_datadog")
    def test_format_error_datadog_fail(
        self, mock_send: mock.Mock, mock_error: mock.Mock
    ):
        """
        Test that when send_error_to_datadog throws an exception, an error is logged.

        `self.assertLogs` was not used because in our settings files, logging is
        disabled when running tests at the Django app level. Testing with mock calls is
        less "correct", but it works in more cases.
        """
        mock_send.side_effect = Exception("Datadog failure.")
        views.DEGraphQLView.format_error(Exception("secret"))
        mock_error.assert_called_once()
