"""Custom views for GraphQL"""

import logging

from graphene_django.views import GraphQLView
from graphql.error import GraphQLError, GraphQLLocatedError
from graphql.error import format_error as format_graphql_error

from django_utils.graphql.errors import (
    format_internal_error,
    format_located_error,
    get_error_path,
    send_error_to_datadog,
)

logger = logging.getLogger(__name__)


class DEGraphQLView(GraphQLView):
    """
    This class wraps the base GraphQL view to format error messages.
    The main purpose is to filter out information that shouldn't be exposed to users.

    There are two levels of errors in GraphQL:
    1) application level errors:
        if the error needs to be rendered, include `errors` in schema.
        every object in that field should be an `Error` that has a code, message (user friendly) and field.

    2) unintentional/server errors:
        these appear in the `errors` list at the root of the graphql response and parallel to `data`,
        these are unhandled server side errors that were "swallowed" by graphene,
        they may be unsafe, and generally not useful to users

    This view deals with the second type of errors, logging them first, then making them opaque.
    """

    @staticmethod
    def format_error(error: Exception) -> dict:
        original_error = error
        if getattr(error, "original_error", None):
            original_error = error.original_error

        try:
            send_error_to_datadog(original_error)
        except Exception:
            logger.exception("Failed to send trace to datadog.")

        if isinstance(error, GraphQLLocatedError):
            error_message = format_located_error(error)
            logger.error("Error in graphql resolver.", exc_info=original_error)
        elif isinstance(error, GraphQLError):
            error_message = format_graphql_error(error)
        else:
            error_message = format_internal_error(error)

        path = get_error_path(error)
        if path:
            error_message.update(path=path)

        return error_message
