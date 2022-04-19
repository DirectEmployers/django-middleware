"""Code for making GraphQL requests from Python."""
from copy import deepcopy
from typing import Any, Dict, Union

import requests
from ddtrace import tracer
from ddtrace.propagation.http import HTTPPropagator
from django.conf import settings
from django.http import HttpRequest


PARTNER_LIBRARY_URL = "http://partner-library:8002/graphql/"


class GraphQLSession(requests.Session):
    """
    Session subclass with a GraphQL-specific request method: `query()`.

    Uses the `requests` library behind the scenes.
    Reference: https://requests.readthedocs.io/en/master/api/#request-sessions

    Sample usage in a Django view:

    ```python
    from django.http import JsonResponse
    from django_utils.graphql.client import GraphQLSession

    def view(request):
        # Create the session class and authorize it from the request
        graphql = GraphQLSession().authorize(request)
        # Make the internal request to a service
        graphql_response = graphql.query("http://deworks-api:8000/graphql/", "query { ping }")
        # Do some error handling...
        # Then return as JSON or whatever
        return JsonResponse(graphql_response)
    ```
    """

    def __init__(self):
        super().__init__()

        # Always expect JSON responses
        self.headers.update({"Accept": "application/json"})

        # Save original headers and cookies
        self._original_headers = deepcopy(self.headers)
        self._original_cookies = deepcopy(self.cookies)

    def authorize(self, request: HttpRequest):
        """
        Add headers and cookies from `request` to the session and return the session.

        Specifically, it adds all the cookies, and these headers from `request`:

        - `Host`
        - `Referer`
        - `X-CSRFToken` (from either the POST body or a pre-existing header)

        Returns the `GraphQLSession`, so it can be chained to the constructor.
        """
        self.headers.update({"Host": request.get_host()})
        self.headers.update({"Referer": request.headers.get("Referer")})

        # CSRF request tokens can come in a POST body or an HTTP header.
        # Since GraphQL uses `application/json`, we put it in a header.
        csrf_post = request.POST.get("csrfmiddlewaretoken")
        csrf_header = request.META.get(settings.CSRF_HEADER_NAME)
        self.headers.update({"X-CSRFToken": csrf_post or csrf_header})

        self.cookies = requests.utils.cookiejar_from_dict(request.COOKIES, self.cookies)

        return self

    def reset_authorization(self):
        """
        Remove any headers and cookies that were added since construction.

        Return `self`
        """
        self.headers = self._original_headers
        self.cookies = self._original_cookies
        return self

    @tracer.wrap()
    def query(
        self,
        endpoint_url: str,
        query_str: str,
        op_name: str = None,
        variables: dict = dict(),
        timeout: Union[float, tuple] = None,
    ) -> Dict[str, Any]:
        """
        Make a POST GraphQL request and return the parsed response.

        Raise `TypeError` if the response is not JSON. Does not raise exceptions on
        HTTP error codes, those must be checked by the caller.

        Based on: https://graphql.org/learn/serving-over-http/
        """
        # Add Datadog trace metadata if it exists.
        span = tracer.current_span()
        if span:
            HTTPPropagator().inject(span.context, self.headers)

        payload = {"query": query_str, "operationName": op_name, "variables": variables}
        response = self.post(endpoint_url, json=payload, timeout=timeout)

        # Check the Content-Type before trying to decode it
        content_type = response.headers["content-type"]
        if not content_type.startswith("application/json"):
            raise TypeError(f"Expected 'application/json', received '{content_type}'.")

        return response.json()
