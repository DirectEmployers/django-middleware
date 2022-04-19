"""Code used for managing GraphQL errors."""
import logging
import os
import re
import traceback
from contextlib import contextmanager
from datetime import datetime
from pprint import pprint
from typing import Dict, List

from ddtrace import tracer
from ddtrace.ext import http
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.utils import IntegrityError
from django.shortcuts import _get_queryset
from graphene import ObjectType, String

from django_utils.graphql.csrf import CsrfException

logger = logging.getLogger(__name__)


"""
This file provides error handling utilities for GraphQL.
Standardized error codes should be defined here
"""

ERROR_BAD_REQUEST = "bad_request"  # equivalent to HTTP 400,
ERROR_PERMISSION_DENIED = "permission_denied"  # this resembles the HTTP 403
ERROR_CSRF_FAILURE = "csrf_detected"  # this is normally a 403 in HTTP, but we can afford a separate code here
ERROR_NOT_FOUND = "not_found"  # 404
ERROR_SERVER_FAILURE = "error"  # 500
ERROR_VALIDATION = "validation_error"
ERROR_INTEGRITY = "integrity_error"
MEMBER_INFO_ERROR_MSG = "Reporting unit does not exist or is not configured correctly"
INVALID_LOCATION_INFORMATION = "Invalid location information passed"


USER_FACING_ERROR_MESSAGES = [MEMBER_INFO_ERROR_MSG]


class GraphQLError(Exception):
    pass


class GraphQLRelayIdError(Exception):
    pass


class Error(ObjectType):
    """
    This is our custom error object for APP LEVEL errors, it has 3 attributes:
    field: which field in a concrete node caused this error
    message: a user friendly message explaining the error
    code: a short string for the error, see definitions above
    """

    field = String()
    message = String()
    code = String()

    def __repr__(self):
        return "%s(code=%s, field=%s, message=%s)" % (
            self.__class__.__name__,
            repr(self.code),
            repr(self.field),
            repr(self.message),
        )

    def __str__(self):
        return "%s(code: %s, field: %s, message: %s)" % (
            self.__class__.__name__,
            self.code,
            self.field,
            self.message,
        )

    def __eq__(self, value):
        return (
            super().__eq__(value)
            and isinstance(value, type(self))
            and self.code == value.code
            and self.field == value.field
            and self.message == value.message
        )


class ErrorWarning(Error):
    pass


# code below are for unintentional errors (the ones should NOT be seen by users).


def get_error_type(error):
    if hasattr(error, "original_error"):
        return "%s:%s" % (type(error).__name__, type(error.original_error).__name__)
    else:
        return type(error).__name__


def get_error_path(error):
    try:
        return ".".join(error.path)
    except (AttributeError, TypeError):
        return ""


def get_request_body(error):
    try:
        return error.source.body
    except AttributeError:
        return ""


def extract_error_info(error):
    error_info = {
        "exception_type": get_error_type(error),
        "error_message": str(error),
        "path": get_error_path(error),
        "request_body": get_request_body(error),
    }
    tb = "".join(traceback.format_list(traceback.extract_tb(error.__traceback__)))
    if tb:
        error_info["traceback"] = tb
    return error_info


def format_internal_error(error):
    """
    formats server error and log it if needed.
    Returns a generic error message when DEBUG is off
    """
    code = ERROR_SERVER_FAILURE

    error_info = extract_error_info(error)
    message = "Something went wrong."
    # only show error messages which are approved user-facing-errors
    if (
        "error_message" in error_info
        and error_info.get("error_message") in USER_FACING_ERROR_MESSAGES
    ):
        message = error_info["error_message"]
    formatted_error = {"code": code, "message": message, "info": error_info}

    # send custom traces to dd
    if settings.DEBUG:
        pprint(formatted_error)

    if getattr(settings, "LOG_GRAPHQL_ERRORS"):
        # send to logging system, need to set `LOG_GRAPHQL_ERRORS`
        error_info.update(
            error_source="GraphQL", timestamp=datetime.utcnow().isoformat()
        )
        logger.exception(error)

    return {"code": code, "message": message}


def format_located_error(error):
    if hasattr(error, "original_error"):
        err = error.original_error
        if isinstance(err, PermissionDenied):
            return {"code": ERROR_PERMISSION_DENIED, "message": str(err)}
        elif isinstance(err, CsrfException):
            return {"code": ERROR_CSRF_FAILURE, "message": str(err)}
        elif isinstance(err, GraphQLError):
            return {"code": ERROR_NOT_FOUND, "message": str(err)}
        elif isinstance(err, GraphQLRelayIdError):
            return {"code": ERROR_BAD_REQUEST, "message": str(err)}

    return format_internal_error(error)


def send_error_to_datadog(error):
    """
    Extract info from the error object and send trace to DataDog
    :param error: a GraphQL error object
    :return: n/a
    """
    resource = "GraphQLError"
    query = getattr(error, "source.body", "")
    field = re.split("[({]", query, 1)[0].strip() or ""
    if field:
        resource = "{} - {}".format(resource, field)

    error_path = get_error_path(error)
    if error_path:
        resource += "." + error_path
    service = os.environ.get("DD_SERVICE", "unknown")
    span = tracer.start_span(name="django.request", service=service, resource=resource)

    error_info = extract_error_info(error)
    span.set_tags(error_info)
    span.set_tag(http.STATUS_CODE, 500)
    span.set_exc_info(type(error), error, error.__traceback__)

    span.finish()


def serializer_errors_to_graphql_errors(serializer):
    return [
        Error(code=ERROR_BAD_REQUEST, message=", ".join(msg), field=err_field)
        for err_field, msg in serializer.errors.items()
    ]


def get_object_or_return_error(klass, *args, **kwargs):
    """
    Works like django.shortcuts.get_object_or_404 but returns an Error on failure.

    Uses get() to return an object, or raises a GraphQLError exception if the object
    does not exist.
    """
    queryset = _get_queryset(klass)
    try:
        return queryset.get(*args, **kwargs)
    except AttributeError:
        klass__name = (
            klass.__name__ if isinstance(klass, type) else klass.__class__.__name__
        )
        raise ValueError(
            "First argument to get_object_or_error() must be a Model, Manager, "
            "or QuerySet, not '%s'." % klass__name
        )
    except queryset.model.DoesNotExist:
        message = "No %s matches the given query." % queryset.model._meta.object_name
        return Error(code=ERROR_NOT_FOUND, message=message, field="")


def get_object_or_return_warning(klass, *args, **kwargs):
    """
    Works like django.shortcuts.get_object_or_404 but only returns an ErrorWarning on failure.

    Uses get() to return an object, or raises a GraphQLError exception if the object
    does not exist.
    """
    queryset = _get_queryset(klass)
    try:
        return queryset.get(*args, **kwargs)
    except AttributeError:
        klass__name = (
            klass.__name__ if isinstance(klass, type) else klass.__class__.__name__
        )
        raise ValueError(
            "First argument to get_object_or_error() must be a Model, Manager, "
            "or QuerySet, not '%s'." % klass__name
        )
    except queryset.model.DoesNotExist:
        message = "No %s matches the given query." % queryset.model._meta.object_name
        return ErrorWarning(code=ERROR_NOT_FOUND, message=message, field="")


def get_object_or_fatal_error(klass, *args, **kwargs):
    """
    Works like django.shortcuts.get_object_or_404

    Uses get() to return an object, or raises a GraphQLError exception if the object
    does not exist.
    """
    queryset = _get_queryset(klass)
    try:
        return queryset.get(*args, **kwargs)
    except AttributeError:
        klass__name = (
            klass.__name__ if isinstance(klass, type) else klass.__class__.__name__
        )
        raise ValueError(
            "First argument to get_object_or_error() must be a Model, Manager, "
            "or QuerySet, not '%s'." % klass__name
        )
    except queryset.model.DoesNotExist:
        raise GraphQLError(
            "No %s matches the given query." % queryset.model._meta.object_name
        )


def check_validation(validators, data, scope=None):
    errors = []

    for validator in validators:
        error = validator(data, scope) if scope else validator(data)
        if error:
            errors.append(error)
            break

    return errors


def validation_error_to_graphql(validation_error: ValidationError) -> List[Error]:
    """
    Take a `ValidationError` with a `message_dict` and convert it to a list of `Error`s.
    """
    errors = []
    for field in validation_error.message_dict:
        for field_message in validation_error.message_dict[field]:
            errors.append(
                Error(field=field, message=field_message, code=ERROR_VALIDATION)
            )
    return errors


def integrity_error_to_graphql(integrity_error: IntegrityError) -> List[Dict[str, str]]:
    """Take an `IntegrityError` and turn it into a dictionary in a list."""
    return [{"code": ERROR_INTEGRITY, "message": str(integrity_error), "field": ""}]


def prefix_error_fields(prefix: str, error: ValidationError) -> ValidationError:
    """Return new ValidationError with a prefix to all the field names."""
    new_error = ValidationError(
        {prefix + key: value for key, value in error.error_dict.items()}
    )
    return new_error


@contextmanager
def error_field_prefix(prefix: str):
    """
    Context manager to catch any `ValidationError`s and add a prefix to their
    `error_dict` fields.
    """
    try:
        yield
    except ValidationError as err:
        if hasattr(err, "error_dict"):
            raise prefix_error_fields(prefix, err) from err
