"""
Tools for making mocks that simplify GraphQL test design for microservice API calls.
"""
import json
from io import BytesIO
from unittest.mock import MagicMock

import requests


def make_mock_request(options: dict = {}):
    """
    Return a function suitable as a side effect for mocking `requests.request()`.

    The options allow you to configure different responses for different URLs.

    - `options`: Dictionary for configuring return values:
      - key (`str`): A URL that is passed to `requests.request()`.
      - value (`dict`): A dictionary of properties of the desired response:
        - `"json"`: The return value of `response.json()`.
        - `"body"`: The body of the response in plain text (ignored if `json` already
        present) (default: `""`).
        - `"status_code"`: The return value of `response.status_code` (default: `200`)

    Example:

    ```python
    make_mock_request({
        "http://user-management:8000/api/user_is_authenticated/": {
            "body": "Internal server error",
            "status_code": 500
        },
        "http://user-management:8000/api/get_user_roles/": {
            "json": {
                "activities": [
                    "read contact",
                    "read partner",
                ]
            },
            "status_code": 200
        },
    })
    ```
    """

    def mock_get(url: str, **kwargs) -> requests.Response:
        """Return a `Response` with the contents defined in `options`."""
        response = requests.Response()
        response.url = url

        if url not in options:
            return MagicMock(spec=response)

        # Fill out the response with details
        response_options = options[url]
        if "json" in response_options:
            raw = BytesIO(bytes(json.dumps(response_options["json"]), "utf-8"))
        else:
            if not isinstance(response_options.get("body", ""), str):
                raise TypeError('The "body" value must be a string.')
            raw = BytesIO(bytes(response_options.get("body", ""), "utf-8"))
        response.raw = raw
        response.status_code = response_options.get("status_code", requests.codes.ok)
        response.headers["Content-Type"] = (
            "application/json" if "json" in response_options else "text/plain"
        )

        return response

    return mock_get


def make_mock_query(options: dict = {}):
    """
    Return a function suitable as a side effect for mocking `GraphQLSession.query()`
    on a per-URL, per-query basis.

    Example:

    ```python
    make_mock_query({
        "https://example.com/graphql": {
            some_query_string: {
                "data": {
                    "node": {
                        "id": 123
                    }
                }
            }
        },
        "https://example.org/graphql": {
            some_other_query_string: {
                "data": {
                    "name": "Ava"
                }
            }
        }
    })
    ```
    """

    def mock_query(endpoint_url: str, query_str: str, *args, **kwargs) -> dict:
        return options[endpoint_url][query_str]

    return mock_query
