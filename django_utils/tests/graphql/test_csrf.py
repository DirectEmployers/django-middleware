"""Test the contents of the shared_library/graphql/csrf.py file."""
from http import cookies

from django.conf import settings
from django.middleware.csrf import get_token
from django.test import override_settings, SimpleTestCase
from django.test.client import RequestFactory

from shared_library.graphql import csrf


class TestCSRFCheck(SimpleTestCase):
    """Test that `csrf_check()` behaves as expected."""

    def setUp(self):
        self.rf = RequestFactory()

    @staticmethod
    def make_cookie_string(simple_cookie: cookies.SimpleCookie) -> str:
        """https://github.com/django/django/blob/eb77e80de01e658541d4fcc3b0b38783ce4e6a7e/django/test/client.py#L284-L287"""
        return "; ".join(
            sorted(
                "%s=%s" % (morsel.key, morsel.coded_value)
                for morsel in simple_cookie.values()
            )
        )

    def test_csrf_processing_done(self):
        """Test that the request is safe if it's already had CSRF testing done."""
        request = self.rf.get("/")
        request.csrf_processing_done = True
        safe, _ = csrf.csrf_check(request)
        self.assertTrue(safe)

    def test_safe_methods(self):
        """Test that safe methods are always safe."""
        safe_methods = ["GET", "HEAD", "OPTIONS", "TRACE"]
        for method in safe_methods:
            with self.subTest(method=method):
                request = self.rf.generic(method, "/")
                safe, _ = csrf.csrf_check(request)
                self.assertTrue(safe)

    def test_fail_non_secure_no_csrf_cookie(self):
        """Test that a non-secure request with no CSRF token is not safe."""
        request = self.rf.post("/", secure=False)
        safe, reason = csrf.csrf_check(request)
        self.assertFalse(safe)
        self.assertEqual(reason, csrf.REASON_NO_CSRF_COOKIE)

    def test_fail_no_referer(self):
        """Test that a request without a referer is not safe."""
        request = self.rf.post("/", secure=True, Referer=None)
        safe, reason = csrf.csrf_check(request)
        self.assertFalse(safe)
        self.assertEqual(reason, csrf.REASON_NO_REFERER)

    def test_fail_malformed_referer(self):
        """Test that a request with a malformed referer is not safe."""
        request = self.rf.post("/", secure=True, HTTP_REFERER="foo bar")
        safe, reason = csrf.csrf_check(request)
        self.assertFalse(safe)
        self.assertEqual(reason, csrf.REASON_MALFORMED_REFERER)

    def test_fail_insecure_referer(self):
        """Test that a request with a non-HTTPS referer is not safe."""
        request = self.rf.post("/", secure=True, HTTP_REFERER="http://example.com")
        safe, reason = csrf.csrf_check(request)
        self.assertFalse(safe)
        self.assertEqual(reason, csrf.REASON_INSECURE_REFERER)

    def test_fail_bad_referer(self):
        """Test that a request with a non-recognized referer is not safe."""
        request = self.rf.post("/", secure=True, HTTP_REFERER="https://example.com")
        safe, reason = csrf.csrf_check(request)
        self.assertFalse(safe)
        self.assertEqual(
            reason, csrf.REASON_BAD_REFERER % request.headers.get("Referer")
        )

    @override_settings(CSRF_TRUSTED_ORIGINS=["testserver"])
    def test_fail_no_csrf_cookie(self):
        """Test that a request without a CSRF cookie is not safe."""
        request = self.rf.post("/", secure=True, HTTP_REFERER="https://testserver")
        safe, reason = csrf.csrf_check(request)
        self.assertFalse(safe)
        self.assertEqual(reason, csrf.REASON_NO_CSRF_COOKIE)

    @override_settings(CSRF_TRUSTED_ORIGINS=["testserver"])
    def test_fail_bad_token(self):
        """Test that a request without a good CSRF token is not safe."""
        C = cookies.SimpleCookie()
        C[settings.CSRF_COOKIE_NAME] = "foo"
        request = self.rf.post(
            "/",
            secure=True,
            HTTP_REFERER="https://testserver",
            HTTP_COOKIE=self.make_cookie_string(C),
        )
        safe, reason = csrf.csrf_check(request)
        self.assertFalse(safe)
        self.assertEqual(reason, csrf.REASON_BAD_TOKEN)

    @override_settings(CSRF_TRUSTED_ORIGINS=["testserver"], CSRF_USE_SESSIONS=False)
    def test_valid_with_csrfmiddlewaretoken(self):
        """Test that a request with a good CSRF in csrfmiddlewaretoken is safe."""
        token = get_token(
            self.rf.post("/", secure=True, HTTP_REFERER="https://testserver")
        )
        C = cookies.SimpleCookie()
        C[settings.CSRF_COOKIE_NAME] = token
        request = self.rf.post(
            "/",
            secure=True,
            HTTP_REFERER="https://testserver",
            HTTP_COOKIE=self.make_cookie_string(C),
            data={"csrfmiddlewaretoken": token},
        )
        safe, reason = csrf.csrf_check(request)
        self.assertTrue(safe, reason)

    @override_settings(CSRF_TRUSTED_ORIGINS=["testserver"], CSRF_USE_SESSIONS=False)
    def test_valid_with_xcsrftoken(self):
        """Test that a request with a good CSRF in X-CSRFToken is safe."""
        token = get_token(
            self.rf.post("/", secure=True, HTTP_REFERER="https://testserver")
        )
        C = cookies.SimpleCookie()
        C[settings.CSRF_COOKIE_NAME] = token
        request = self.rf.post(
            "/",
            secure=True,
            HTTP_REFERER="https://testserver",
            HTTP_COOKIE=self.make_cookie_string(C),
            **{settings.CSRF_HEADER_NAME: token},
        )
        safe, reason = csrf.csrf_check(request)
        self.assertTrue(safe, reason)

    @override_settings(CSRF_USE_SESSIONS=False, CSRF_COOKIE_DOMAIN="testserver")
    def test_valid_csrf_cookie_domain(self):
        """Test that a request from CSRF_COOKIE_DOMAIN is valid."""
        token = get_token(
            self.rf.post("/", secure=True, HTTP_REFERER="https://testserver")
        )
        C = cookies.SimpleCookie()
        C[settings.CSRF_COOKIE_NAME] = token
        request = self.rf.post(
            "/",
            secure=True,
            HTTP_REFERER="https://testserver",
            HTTP_COOKIE=self.make_cookie_string(C),
            **{settings.CSRF_HEADER_NAME: token},
        )
        safe, reason = csrf.csrf_check(request)
        self.assertTrue(safe, reason)

    @override_settings(CSRF_USE_SESSIONS=False, CSRF_COOKIE_DOMAIN="testserver")
    def test_valid_csrf_cookie_domain_strange_port(self):
        """Test that a request from CSRF_COOKIE_DOMAIN is valid even with a port that isn't 80 or 443."""
        token = get_token(
            self.rf.post("/", secure=True, HTTP_REFERER="https://testserver")
        )
        C = cookies.SimpleCookie()
        C[settings.CSRF_COOKIE_NAME] = token
        request = self.rf.post(
            "/",
            SERVER_PORT="8080",
            secure=True,
            HTTP_REFERER="https://testserver:8080",
            HTTP_COOKIE=self.make_cookie_string(C),
            **{settings.CSRF_HEADER_NAME: token},
        )
        safe, reason = csrf.csrf_check(request)
        self.assertTrue(safe, reason)
