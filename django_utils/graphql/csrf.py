"""Code for enforcing cross-site request forgery protection."""

from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpRequest
from django.middleware.csrf import _sanitize_token
from django.utils.crypto import constant_time_compare
from django.utils.encoding import force_str
from django.utils.http import is_same_domain

REASON_NO_REFERER = "Referer checking failed - no Referer."
REASON_BAD_REFERER = "Referer checking failed - %s does not match any trusted origins."
REASON_NO_CSRF_COOKIE = "CSRF cookie not set."
REASON_BAD_TOKEN = "CSRF token missing or incorrect."
REASON_MALFORMED_REFERER = "Referer checking failed - Referer is malformed."
REASON_INSECURE_REFERER = (
    "Referer checking failed - Referer is insecure while host is secure."
)

CSRF_KEY_LENGTH = 32


class CsrfException(Exception):
    """request failed CSRF check, go away now"""

    pass


def csrf_check(request: HttpRequest) -> (bool, str):
    """
    Code below is based on the django CSRF guide/middleware,
    with slight modifications so it works here with graphene

    :param request: the request to be verified
    :return: whether the request is safe (True/False) + Reason
    """

    # avoid validating a request multiple times
    if getattr(request, "csrf_processing_done", False):
        return True, ""

    try:
        csrf_token = _sanitize_token(request.COOKIES[settings.CSRF_COOKIE_NAME])
        # Use same token next time
        request.META["CSRF_COOKIE"] = csrf_token
    except KeyError:
        csrf_token = None

    # Assume that anything not defined as 'safe' by RFC7231 needs protection
    if request.method not in ("GET", "HEAD", "OPTIONS", "TRACE"):
        if request.is_secure():
            referer = force_str(
                request.headers.get("Referer"), strings_only=True, errors="replace"
            )
            if referer is None:
                return False, REASON_NO_REFERER

            referer = urlparse(referer)

            # Make sure we have a valid URL for Referer.
            if "" in (referer.scheme, referer.netloc):
                return False, REASON_MALFORMED_REFERER

            # Ensure that our Referer is also secure.
            if referer.scheme != "https":
                return False, REASON_INSECURE_REFERER

            # If there isn't a CSRF_COOKIE_DOMAIN, assume we need an exact
            # match on host:port. If not, obey the cookie rules.
            if settings.CSRF_COOKIE_DOMAIN is None:
                # request.get_host() includes the port.
                good_referer = request.get_host()
            else:
                good_referer = settings.CSRF_COOKIE_DOMAIN
                server_port = request.get_port()
                if server_port not in ("443", "80"):
                    good_referer = "%s:%s" % (good_referer, server_port)

            # Here we generate a list of all acceptable HTTP referers,
            # including the current host since that has been validated
            # upstream.
            good_hosts = list(settings.CSRF_TRUSTED_ORIGINS)
            good_hosts.append(good_referer)

            if not any(is_same_domain(referer.netloc, host) for host in good_hosts):
                reason = REASON_BAD_REFERER % referer.geturl()
                return False, reason

        if csrf_token is None:
            # No CSRF cookie. For POST requests, we insist on a CSRF cookie,
            # and in this way we can avoid all CSRF attacks, including login
            # CSRF.
            return False, REASON_NO_CSRF_COOKIE

        # Check non-cookie token for match.
        request_csrf_token = ""
        if request.method == "POST":
            try:
                request_csrf_token = request.POST.get("csrfmiddlewaretoken", "")
            except IOError:
                pass

        if request_csrf_token == "":
            # Fall back to X-CSRFToken, to make things easier for AJAX,
            # and possible for PUT/DELETE.
            request_csrf_token = request.META.get(settings.CSRF_HEADER_NAME, "")

        if not constant_time_compare(request_csrf_token, csrf_token):
            return False, REASON_BAD_TOKEN

    request.csrf_processing_done = True
    return True, ""
