"""Decorators for Graphene resolvers."""
from functools import wraps
from typing import Callable, List, TypeVar

import requests
from ddtrace import tracer
from django.core.exceptions import PermissionDenied
from django.core.handlers.wsgi import WSGIRequest
from graphql.execution.base import ResolveInfo

from django_utils.graphql.csrf import CsrfException, csrf_check

MISSING_CONTEXT_MSG = "Cannot do anything without a resolver context."


def get_context_or_fail(info: ResolveInfo) -> WSGIRequest:
    """
    Raise `ValueError` if `info` doesn't have a `context` attribute.
    """
    if not hasattr(info, "context"):
        raise ValueError(MISSING_CONTEXT_MSG)
    return info.context


Resolver = TypeVar("Resolver", bound=Callable)


def requires_authentication(resolver):
    """
    Decorator which raises `PermissionDenied` if the session's user is not logged in.

    The difference between this and the `requires_authentication` from
    `graphql_myjobs.decorators` is that this one sends an API request to the
    `user-management` pod to determine the state of the user, without having to
    reference a `User` instance (forbidden in `django_utils`).
    """

    @wraps(resolver)
    def decorator(root, info, **kwargs):
        context = get_context_or_fail(info)
        url = "http://user-management:8000/api/user_is_authenticated/"
        response = requests.get(url, cookies=context.COOKIES)
        try:
            response.raise_for_status()
        except requests.HTTPError as err:
            raise PermissionDenied("Permission Denied. Please log in first.") from err
        is_authenticated = response.json().get("isAuthenticated", False)
        if not is_authenticated:
            raise PermissionDenied("Permission Denied. Please log in first.")
        return resolver(root, info, **kwargs)

    return decorator


def requires_csrf_check(resolver):
    """
    Decorator which raises `CsrfException` if the request's CSRF data is bad or missing.
    """

    @wraps(resolver)
    def decorator(root, info, **kwargs):
        csrf_safe, reason = csrf_check(get_context_or_fail(info))
        if not csrf_safe:
            raise CsrfException(reason)
        return resolver(root, info, **kwargs)

    return decorator


def get_user_permissions(incoming_request) -> dict:
    """
    Query the `get_user_roles` API using the cookies included in the incoming request.

    Returns a set of strings representing the activities the user can perform.

    Raises `requests.HTTPError` if an error occurred while calling the API.

    API defined at `myjobs.usermanagement.api_get_activities_by_company_and_user`.
    """
    url = "http://user-management:8000/api/get_user_roles/"
    response = requests.get(url, cookies=incoming_request.COOKIES)
    response.raise_for_status()
    if response.headers["Content-Type"] != "application/json":
        raise requests.HTTPError(
            "Invalid content-type '%s' returned" % response.headers["Content-Type"]
        )
    return response.json()


def _requires_activities(info, activities, require_is_staff, require_is_superuser):
    """
    If the user doesn't have all the required activities, raise `PermissionDenied`.
    """
    incoming_request = get_context_or_fail(info)
    try:
        permissions = get_user_permissions(incoming_request)
        user_activities = set(permissions["activities"])
        user_attributes = permissions["user"]
    except requests.HTTPError as err:
        raise PermissionDenied("Permission Denied.") from err
    if not activities.issubset(user_activities):
        missing = activities - user_activities
        raise PermissionDenied(
            f"Missing required activit{'ies' if len(missing) > 1 else 'y'}: {', '.join(missing)}"
        )
    if not user_attributes["is_staff"] and require_is_staff:
        raise PermissionDenied("User must be staff to take this action")
    if not user_attributes["is_superuser"] and require_is_superuser:
        raise PermissionDenied("User must be a superuser to take this action")


def requires_activities(
    *activities: List[str], require_is_staff=False, require_is_superuser=False
):
    """
    Decorator which raises `PermissionDenied` if the current django-session is missing
    permissions. Sends a request to the user-management pod to get the current session's
    allowed activities and user traits, and validates that all requirements are met.
    :param activities: list of strings; Activities which are required to perfomr this
        action. If any activities are missing, raises a exception.
    :param require_is_staff: boolean; if True, the user must be staff to take this
        action.
    :param require_is_superuser: boolean; if True, the user must be a superuser to take
        this action.
    :return:
    """
    activities = set(activities)

    def decorator(resolver):
        @wraps(resolver)
        def wrapped(root, info, *args, **kwargs):
            _requires_activities(
                info, activities, require_is_staff, require_is_superuser
            )
            return resolver(root, info, *args, **kwargs)

        return wrapped

    return decorator


def get_queryset_requires_activities(
    *activities: List[str], require_is_staff=False, require_is_superuser=False
):
    """
    Decorator for graphene's `get_queryset`, which raises `PermissionDenied` if the
    current django-session is missing any required permissions. Sends a request to the
    user-management pod to get the current session's allowed activities and user traits,
    and validates that all requirements are met.
    :param activities: list of strings; Activities which are required to perform this
        action. If any activities are missing, raises a exception.
    :param require_is_staff: boolean; if True, the user must be staff to take this
        action.
    :param require_is_superuser: boolean; if True, the user must be a superuser to take
        this action.
    :return:
    """
    activities = set(activities)

    def decorator(resolver):
        @wraps(resolver)
        def wrapped(cls, queryset, info):
            _requires_activities(
                info, activities, require_is_staff, require_is_superuser
            )
            return resolver(cls, queryset, info)

        return wrapped

    return decorator


def trace_resolver(resolver: Resolver) -> Resolver:
    """
    Decorator for Graphene resolvers to enhance Datadog tracing.
    """

    @wraps(resolver)
    def _wrapped(*args, **kwargs):
        span = tracer.current_span()
        service_name = None
        if span:
            service_name = span.service

        # Ensure that service_name is defined
        if service_name is None:
            service_name = "unknown"

        # Add graphql suffix if it doesn't already have it
        graphql_service_name = (
            service_name + ".graphql"
            if not service_name.endswith(".graphql")
            else service_name
        )

        with tracer.trace(
            "graphql.graphql",
            service=graphql_service_name,
            resource=resolver.__qualname__,
        ):
            return resolver(*args, **kwargs)

    return _wrapped
