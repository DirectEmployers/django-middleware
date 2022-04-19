from unittest.mock import patch, MagicMock

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from shared_library.graphql.csrf import REASON_BAD_TOKEN, REASON_NO_CSRF_COOKIE
from shared_library.graphql.decorators import (
    MISSING_CONTEXT_MSG,
    get_context_or_fail,
    requires_activities,
    get_queryset_requires_activities,
    requires_authentication,
    requires_csrf_check,
)
from shared_library.graphql.testing_mocks import make_mock_request

CSRF_MIDDLEWARE_NAME = "csrfmiddlewaretoken"


def mocked_resolver(root, info):
    return "continue"


class MockedUser(object):
    def __init__(self, authenticated=False):
        self.authenticated = authenticated

    def is_authenticated(self):
        return self.authenticated


class MockedContext(object):
    """Mocking an HTTP request object"""

    def __init__(self, user=None, csrf_token=None, csrf_match=False, secure=False):
        self.user = user
        self.csrf_token = csrf_token
        self.method = "POST"
        self.POST = {}
        self.COOKIES = {}
        self.META = {}

        if csrf_token:
            self.COOKIES[settings.CSRF_COOKIE_NAME] = csrf_token
        if csrf_match:
            self.POST[CSRF_MIDDLEWARE_NAME] = csrf_token
            self.META[settings.CSRF_HEADER_NAME] = csrf_token
        else:
            self.POST[CSRF_MIDDLEWARE_NAME] = "no_match"

        self.secure = secure

    def is_secure(self):
        return self.secure


class MockedInfo(object):
    def __init__(self, context):
        if context is not None:
            self.context = context


class GraphQLDecoratorTests(TestCase):
    def test_missing_context_causes_exception(self):
        info = MockedInfo(context=None)
        with self.assertRaisesMessage(ValueError, MISSING_CONTEXT_MSG):
            get_context_or_fail(info)

    def test_csrf_missing_token_should_be_rejected(self):
        context = MockedContext(csrf_token=None)
        info = MockedInfo(context=context)
        with self.assertRaisesMessage(Exception, REASON_NO_CSRF_COOKIE):
            requires_csrf_check(mocked_resolver)({}, info)

    def test_csrf_host_mismatch_should_be_rejected(self):
        context = MockedContext(csrf_token="superinsecure", csrf_match=False)
        info = MockedInfo(context=context)
        with self.assertRaisesMessage(Exception, REASON_BAD_TOKEN):
            requires_csrf_check(mocked_resolver)({}, info)

    def test_good_request_should_continue(self):
        context = MockedContext(
            csrf_token="Z7rdPDt33n0eLXU9yuOhfGZaJWQBlLUChpJv7VLllFiw3fcrQM6zxYhs1e8TD3cU",
            csrf_match=True,
        )
        info = MockedInfo(context=context)
        result = requires_csrf_check(mocked_resolver)({}, info)
        self.assertEqual("continue", result)

    @patch("shared_library.graphql.decorators.requests.get")
    def test_requires_activities(self, mock_get):
        """
        Test that the requires_activities decorator raises PermissionDenied on an
        activities mismatch.
        """
        # Create a mock response for the get_user_roles API
        mock_get.side_effect = make_mock_request(
            {
                "http://user-management:8000/api/get_user_roles/": {
                    "json": {
                        "activities": ["activity b", "activity c"],
                        "user": {"is_staff": False, "is_superuser": False},
                    }
                }
            }
        )

        # Create the resolver and decorate it
        @requires_activities("activity a", "activity b")
        def resolver(root, info, *kwargs):
            return True

        info = MockedInfo(MockedContext())

        with self.assertRaisesRegex(PermissionDenied, "activity a"):
            resolver({}, info)

    @patch("shared_library.graphql.decorators.requests.get")
    def test_requires_activities_success(self, mock_get):
        """
        Test that the requires_activities decorator doesn't raise PermissionDenied on an
        activities match.
        """
        # Create a mock response for the get_user_roles API
        mock_get.side_effect = make_mock_request(
            {
                "http://user-management:8000/api/get_user_roles/": {
                    "json": {
                        "activities": ["activity b", "activity a"],
                        "user": {"is_staff": False, "is_superuser": False},
                    }
                }
            }
        )

        # Create the resolver and decorate it
        @requires_activities("activity a", "activity b")
        def resolver(root, info, *kwargs):
            return True

        info = MockedInfo(MockedContext())

        self.assertTrue(resolver({}, info))

    @patch("shared_library.graphql.decorators.requests.get")
    def test_requires_authentication(self, mock_get):
        """
        Test that `requires_authentication` raises `PermissionError` when the API
        returns False.
        """
        # Create a mock response for the user_is_authenticated API
        mock_get.side_effect = make_mock_request(
            {
                "http://user-management:8000/api/user_is_authenticated/": {
                    "json": {"isAuthenticated": False}
                }
            }
        )

        # Create the resolver and decorate it
        @requires_authentication
        def resolver(root, info, *kwargs):
            return True

        info = MockedInfo(MockedContext())

        with self.assertRaises(PermissionDenied):
            resolver({}, info)

    @patch("shared_library.graphql.decorators.requests.get")
    def test_requires_authentication_success(self, mock_get):
        """
        Test that `requires_authentication` doesn't raise `PermissionError` when the API
        returns True.
        """
        # Create a mock response for the user_is_authenticated API
        mock_get.side_effect = make_mock_request(
            {
                "http://user-management:8000/api/user_is_authenticated/": {
                    "json": {"isAuthenticated": True}
                }
            }
        )

        # Create the resolver and decorate it
        @requires_authentication
        def resolver(root, info, *kwargs):
            return True

        info = MockedInfo(MockedContext())

        self.assertTrue(resolver({}, info))

    @patch("shared_library.graphql.decorators.requests.get")
    def test_requires_activities_requires_is_staff_fails(self, mock_get):
        """
        Tests that @requires_activities raises an exception if is_staff is required,
        but is not returned by the user-management pod
        """
        # Create a mock response for the get_user_roles API
        mock_get.side_effect = make_mock_request(
            {
                "http://user-management:8000/api/get_user_roles/": {
                    "json": {
                        "activities": ["activity b", "activity c"],
                        "user": {"is_staff": False, "is_superuser": False},
                    }
                }
            }
        )

        # Create the resolver and decorate it
        @requires_activities("activity b", require_is_staff=True)
        def resolver(root, info, *kwargs):
            return True

        info = MockedInfo(MockedContext())

        with self.assertRaisesRegex(PermissionDenied, "staff"):
            resolver({}, info)

    @patch("shared_library.graphql.decorators.requests.get")
    def test_requires_activities_requires_is_superuser_fails(self, mock_get):
        """
        Tests that @requires_activities raises an exception if is_superuser is required,
        but is not returned by the user-management pod
        """
        # Create a mock response for the get_user_roles API
        mock_get.side_effect = make_mock_request(
            {
                "http://user-management:8000/api/get_user_roles/": {
                    "json": {
                        "activities": ["activity b", "activity c"],
                        "user": {"is_staff": False, "is_superuser": False},
                    }
                }
            }
        )

        # Create the resolver and decorate it
        @requires_activities("activity b", require_is_superuser=True)
        def resolver(root, info, *kwargs):
            return True

        info = MockedInfo(MockedContext())

        with self.assertRaisesRegex(PermissionDenied, "superuser"):
            resolver({}, info)

    @patch("shared_library.graphql.decorators.requests.get")
    def test_requires_activities_requires_is_staff_passes(self, mock_get):
        """
        Tests that @requires_activities passes if is_staff is required, and is returned
        by the user-management pod
        """
        # Create a mock response for the get_user_roles API
        mock_get.side_effect = make_mock_request(
            {
                "http://user-management:8000/api/get_user_roles/": {
                    "json": {
                        "activities": ["activity b", "activity c"],
                        "user": {"is_staff": True, "is_superuser": False},
                    }
                }
            }
        )

        # Create the resolver and decorate it
        @requires_activities("activity b", require_is_staff=True)
        def resolver(root, info, *kwargs):
            return True

        info = MockedInfo(MockedContext())

        try:
            resolver({}, info)
        except PermissionDenied as e:
            self.fail("permission error should not be raised: %s" % str(e))

    @patch("shared_library.graphql.decorators.requests.get")
    def test_requires_activities_requires_is_superuser_passes(self, mock_get):
        """
        Tests that @requires_activities passes if is_superuser is required, and is
        returned by the user-management pod
        """
        # Create a mock response for the get_user_roles API
        mock_get.side_effect = make_mock_request(
            {
                "http://user-management:8000/api/get_user_roles/": {
                    "json": {
                        "activities": ["activity a", "activity b"],
                        "user": {"is_staff": False, "is_superuser": True},
                    }
                }
            }
        )

        # Create the resolver and decorate it
        @requires_activities("activity a", require_is_superuser=True)
        def resolver(root, info, *kwargs):
            return True

        info = MockedInfo(MockedContext())

        try:
            resolver({}, info)
        except PermissionDenied as e:
            self.fail("permission error should not be raised: %s" % str(e))

    @patch("shared_library.graphql.decorators.requests.get")
    def test_requires_activities_requires_no_activities_passes(self, mock_get):
        """
        Tests that require_activities works if no activities are passed, but some
        optional flags are passed
        """
        # Create a mock response for the get_user_roles API
        mock_get.side_effect = make_mock_request(
            {
                "http://user-management:8000/api/get_user_roles/": {
                    "json": {
                        "activities": [],
                        "user": {"is_staff": True, "is_superuser": True},
                    }
                }
            }
        )

        # Create the resolver and decorate it
        @requires_activities(require_is_staff=True, require_is_superuser=True)
        def resolver(root, info, *kwargs):
            return True

        info = MockedInfo(MockedContext())

        try:
            resolver({}, info)
        except PermissionDenied as e:
            self.fail("permission error should not be raised: %s" % str(e))

    @patch("shared_library.graphql.decorators.requests.get")
    def test_requires_activities_requires_no_activities_fails(self, mock_get):
        """
        Tests that require_activities works if no activities are passed, but some
        optional flags are passed
        """
        # Create a mock response for the get_user_roles API
        mock_get.side_effect = make_mock_request(
            {
                "http://user-management:8000/api/get_user_roles/": {
                    "json": {
                        "activities": [],
                        "user": {"is_staff": True, "is_superuser": False},
                    }
                }
            }
        )

        # Create the resolver and decorate it
        @requires_activities(require_is_staff=True, require_is_superuser=True)
        def resolver(root, info, *kwargs):
            return True

        info = MockedInfo(MockedContext())

        with self.assertRaisesRegex(PermissionDenied, "superuser"):
            resolver({}, info)

    @patch("shared_library.graphql.decorators.requests.get")
    def test_requires_activities_requires_http_status_error(self, mock_get):
        """
        Tests that the @requires_activities decorator raises a PermissionDenied
        exception if it catches an HTTPError from the user-management pod
        """
        # Create a mock response for the get_user_roles API
        mock_get.side_effect = make_mock_request(
            {
                "http://user-management:8000/api/get_user_roles/": {
                    "json": {
                        "activities": [],
                        "user": {"is_staff": True, "is_superuser": True},
                    },
                    "status_code": 400,
                }
            }
        )

        # Create the resolver and decorate it
        @requires_activities(require_is_staff=True, require_is_superuser=True)
        def resolver(root, info, *kwargs):
            return True

        info = MockedInfo(MockedContext())

        with self.assertRaises(PermissionDenied):
            resolver({}, info)

    @patch("shared_library.graphql.decorators.requests.get")
    def test_requires_activities_requires_http_content_error(self, mock_get):
        """
        Tests that the @requires_activities decorator raises a PermissionDenied
        exception if it catches an HTTPError from the user-management pod
        """
        # Create a mock response for the get_user_roles API
        mock_get.side_effect = make_mock_request(
            {
                "http://user-management:8000/api/get_user_roles/": {
                    "body": "<h1> TEST ERROR </h1>"
                }
            }
        )

        # Create the resolver and decorate it
        @requires_activities(require_is_staff=True, require_is_superuser=True)
        def resolver(root, info, *kwargs):
            return True

        info = MockedInfo(MockedContext())

        with self.assertRaises(PermissionDenied):
            resolver({}, info)


class TestRequiredActivitiesBase(TestCase):
    def setUp(self):
        self.info = MockedInfo(MockedContext())

    @classmethod
    def get_mock_response(cls, *activities, is_staff=False, is_superuser=False):
        return make_mock_request(
            {
                "http://user-management:8000/api/get_user_roles/": {
                    "json": {
                        "activities": activities,
                        "user": {"is_staff": is_staff, "is_superuser": is_superuser},
                    }
                }
            }
        )


class TestQuerysetRequiresActivities(TestRequiredActivitiesBase):
    @patch("shared_library.graphql.decorators.requests.get")
    def test_queryset_requires_activities_passes_all(self, mock_get):
        """
        Tests that @get_queryset_requires_activities passes if all possible requirements
        are required, and also satisfied.
        """
        mock_get.side_effect = self.get_mock_response(
            "one", "two", "three", is_staff=True, is_superuser=True
        )

        @get_queryset_requires_activities(
            "one", "three", require_is_staff=True, require_is_superuser=True
        )
        def resolver(cls, queryset, info):
            return True

        try:
            resolver(MagicMock(), MagicMock(), self.info)
        except PermissionDenied as e:
            self.fail("permission error should not be raised: %s" % str(e))

    @patch("shared_library.graphql.decorators.requests.get")
    def test_queryset_requires_activities_passes_activities(self, mock_get):
        """
        Tests the @get_queryset_requires_activities passes if all the required
        activities are passed.
        """
        mock_get.side_effect = self.get_mock_response("one", "two", "three")

        @get_queryset_requires_activities("one", "three")
        def resolver(cls, queryset, info):
            return True

        try:
            resolver(MagicMock(), MagicMock(), self.info)
        except PermissionDenied as e:
            self.fail("permission error should not be raised: %s" % str(e))

    @patch("shared_library.graphql.decorators.requests.get")
    def test_queryset_requires_activities_passes_is_staff(self, mock_get):
        """
        Tests that @get_queryset_requires_activities passes if is_staff is both required
        and satisfied.
        """
        mock_get.side_effect = self.get_mock_response(is_staff=True)

        @get_queryset_requires_activities(require_is_staff=True)
        def resolver(cls, queryset, info):
            return True

        try:
            resolver(MagicMock(), MagicMock(), self.info)
        except PermissionDenied as e:
            self.fail("permission error should not be raised: %s" % str(e))

    @patch("shared_library.graphql.decorators.requests.get")
    def test_queryset_requires_activities_passes_is_superuser(self, mock_get):
        """
        Tests that @get_queryset_requires_activities passes if is_superuser is both
        required, and satisfied.
        """
        mock_get.side_effect = self.get_mock_response(is_superuser=True)

        @get_queryset_requires_activities(require_is_superuser=True)
        def resolver(cls, queryset, info):
            return True

        try:
            resolver(MagicMock(), MagicMock(), self.info)
        except PermissionDenied as e:
            self.fail("permission error should not be raised: %s" % str(e))

    @patch("shared_library.graphql.decorators.requests.get")
    def test_queryset_requires_activities_missing_activity(self, mock_get):
        """
        Tests that @get_queryset_requires_activities will raise an exception if an
        activity that is required is not  returned by the user-management pod.
        """
        mock_get.side_effect = self.get_mock_response("one", "two")

        @get_queryset_requires_activities("one", "activity three")
        def resolver(cls, queryset, info):
            return True

        with self.assertRaisesRegex(PermissionDenied, "activity three"):
            resolver(MagicMock(), MagicMock(), self.info)

    @patch("shared_library.graphql.decorators.requests.get")
    def test_queryset_requires_activities_missing_is_staff(self, mock_get):
        """
        Tests that @get_queryset_requires_activities will raise an exception if is_staff
        is required but not  returned by the user-management pod.
        """
        mock_get.side_effect = self.get_mock_response("one", "two", is_superuser=True)

        @get_queryset_requires_activities(require_is_staff=True)
        def resolver(cls, queryset, info):
            return True

        with self.assertRaisesRegex(PermissionDenied, "staff"):
            resolver(MagicMock(), MagicMock(), self.info)

    @patch("shared_library.graphql.decorators.requests.get")
    def test_queryset_requires_activities_missing_is_superuser(self, mock_get):
        """
        Tests that @get_queryset_requires_activities raises an exception if is_superuser
        is required, but not returned by the user-management pod
        """
        mock_get.side_effect = self.get_mock_response(is_staff=True)

        @get_queryset_requires_activities(require_is_superuser=True)
        def resolver(cls, queryset, info):
            return True

        with self.assertRaisesRegex(PermissionDenied, "superuser"):
            resolver(MagicMock(), MagicMock(), self.info)

    @patch("shared_library.graphql.decorators.requests.get")
    def test_queryset_requires_activities_http_status_error(self, mock_get):
        """
        Tests that the @get_queryset_requires_activities decorator raises a
        PermissionDenied exception if it catches an HTTPError from the user-management
        pod
        """
        mock_get.side_effect = make_mock_request(
            {
                "http://user-management:8000/api/get_user_roles/": {
                    "json": {
                        "activities": [],
                        "user": {"is_staff": True, "is_superuser": True},
                    },
                    "status_code": 400,
                }
            }
        )

        @get_queryset_requires_activities(require_is_superuser=True)
        def resolver(cls, queryset, info):
            return True

        with self.assertRaises(PermissionDenied):
            resolver(MagicMock(), MagicMock(), self.info)

    @patch("shared_library.graphql.decorators.requests.get")
    def test_queryset_requires_activities_http_content_error(self, mock_get):
        """
        Tests that the @get_queryset_requires_activities decorator raises a
        PermissionDenied exception if it catches an HTTPError from the user-management
        pod
        """
        mock_get.side_effect = make_mock_request(
            {
                "http://user-management:8000/api/get_user_roles/": {
                    "body": "<h1> TEST ERROR </h1>"
                }
            }
        )

        @get_queryset_requires_activities(require_is_superuser=True)
        def resolver(cls, queryset, info):
            return True

        with self.assertRaises(PermissionDenied):
            resolver(MagicMock(), MagicMock(), self.info)
