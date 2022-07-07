"""Django middleware for simple health checks.

Requires Django 3.2+.

HealthCheckMiddleware courtesy of:
https://www.ianlewis.org/en/kubernetes-health-checks-django
"""

import logging

from django.http import HttpResponse, HttpResponseServerError


HEALTHZ_ENDPOINT = "/healthz"
READINESS_ENDPOINT = "/readiness"


def msg_filter(record):
    if (
        HEALTHZ_ENDPOINT in record.getMessage()
        or READINESS_ENDPOINT in record.getMessage()
    ):
        return 0
    return 1


logger = logging.getLogger("django.server")
logger.addFilter(msg_filter)


def check_readiness():
    """Raise as exception if the server is not ready."""

    # Connect to each database and do a generic standard SQL query that doesn't
    # write any data and doesn't depend on any tables being present.
    try:
        from django.db import connections

        for name in connections:
            cursor = connections[name].cursor()
            cursor.execute("SELECT 1;")
            row = cursor.fetchone()
            if row is None:
                return HttpResponseServerError("db: invalid response")
    except Exception as e:
        logger.exception(e)
        return HttpResponseServerError("db: cannot connect to database.")

    # Call get_stats() to connect to each memcached instance and get its stats.
    # This can effectively check if each is online.
    try:
        from django.core.cache import caches
        from django.core.cache.backends.memcached import BaseMemcachedCache

        for cache in caches.all():
            if isinstance(cache, BaseMemcachedCache):
                stats = cache._cache.get_stats()
                if len(stats) != len(cache._servers):
                    return HttpResponseServerError("cache: cannot connect to cache.")
    except Exception as e:
        logger.exception(e)
        return HttpResponseServerError("cache: cannot connect to cache.")


class HealthCheckMiddleware:
    """Simple Django health check endpoints.

    Endpoints:
    healthz/    Responds with 200 OK if server can return a simple response.
    readiness/  Responds with 200 OK if requisite databases and caches are ready.
    """

    endpoints = (
        HEALTHZ_ENDPOINT,
        READINESS_ENDPOINT,
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method != "GET" or request.path not in self.endpoints:
            # Passthrough if we aren't accessing health checks.
            return self.get_response(request)

        if request.path == "/readiness":
            # Throw an exception if checks don't pass.
            check_readiness()

        # Return a simple 200 OK response.
        return HttpResponse("OK")
