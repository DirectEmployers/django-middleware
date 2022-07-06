"""Django middleware for simple health checks.

Requires Django 3.2+.

HealthCheckMiddleware courtesy of:
https://www.ianlewis.org/en/kubernetes-health-checks-django
"""

import logging

from django.http import HttpResponse, HttpResponseServerError

logger = logging.getLogger("healthz")


class HealthCheckMiddleware:
    """Simple Django health check endpoints.

    Endpoints:
    healthz/    Responds with 200 OK if server can return a simple response.
    readiness/  Responds with 200 OK if requisite databases and caches are ready.
    """

    healthz_endpoint = "/healthz"
    readiness_endpoint = "/readiness"

    endpoints = [healthz_endpoint, readiness_endpoint]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        if request.method == "GET" and request.path in self.endpoints:
            # Disable DEBUG and INFO logs when responding to these endpoints.
            orig_level = logging.root.getEffectiveLevel()
            logging.disable(logging.INFO)

            if request.path == "/readiness":
                response = self.readiness(request)
            else:
                response = self.healthz(request)

            # Restore logging level.
            logging.disable(orig_level)

            return response

        return self.get_response(request)

    def healthz(self, request):
        """
        Returns that the server is alive.
        """
        return HttpResponse("OK")

    def readiness(self, request):
        """
        Returns that the server is ready to receive requests/connections.
        """

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
                        return HttpResponseServerError(
                            "cache: cannot connect to cache."
                        )
        except Exception as e:
            logger.exception(e)
            return HttpResponseServerError("cache: cannot connect to cache.")

        return self.healthz(request)
