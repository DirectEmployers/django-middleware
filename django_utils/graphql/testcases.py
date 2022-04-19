"""Testcases for GraphQL testing."""
from typing import Optional

from django.http import HttpResponse
from graphene_django.utils.testing import GraphQLTestCase


class EnhancedGraphQLTestCase(GraphQLTestCase):
    """
    GraphQLTestCase with compatibility fixes and convenience methods.

    Note: The client for this test case is `self._client`, not `self.client`.
    """

    def assertResponseNoErrors(self, resp: HttpResponse):
        """
        Assert that the call went through correctly.

        HTTP status 200 means the syntax is ok. If there are no `errors`, the call was
        fine.

        Subclassed to display the errors on failure.
        """
        try:
            content = resp.json()
        except ValueError as err:
            msg = "Response wasn't JSON: %s" % resp.content.decode()
            raise ValueError(msg) from err
        self.assertEqual(resp.status_code, 200, content.get("errors"))
        self.assertNotIn("errors", content.keys(), content.get("errors"))

    def run_query(
        self,
        query: str,
        op_name: str = None,
        input_data: dict = None,
        variables: dict = None,
        headers: dict = None,
        expect_errors: Optional[bool] = False,
    ) -> dict:
        """
        Run a query, test its response, return parsed response content.

        `expect_errors` accepts three different values:
        1. `True`: Assert there is a top-level "errors" key
        2. `False`: Assert there is NOT a top-level "errors" key (default)
        3. `None`: Don't do any assertion testing on the response.

        See `graphene_django.utils.testing.GraphQLTestCase.query` for the meaning of
        the other arguments.
        """
        response = self.query(
            query,
            op_name=op_name,
            input_data=input_data,
            variables=variables,
            headers=headers,
        )
        if expect_errors is True:
            self.assertResponseHasErrors(response)
        elif expect_errors is False:
            self.assertResponseNoErrors(response)
        return response.json()
