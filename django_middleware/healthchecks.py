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
        return record.levelno > logging.INFO
    return 1


logger = logging.getLogger("django.server")
logger.addFilter(msg_filter)


def databases_ready() -> bool:
    """Check health of database connections.

    Connect to each database and do a generic standard SQL query that doesn't write
    any data and doesn't depend on any tables being present.
    """
    from django.db import connections as dbs

    ready = True
    databases = {alias: dbs[alias] for alias in dbs}

    for name, conn in databases.items():
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1;")

            if cursor.fetchone() is None:
                ready = False
                logger.error(f"Database: Invalid response from '{name}'")
        except Exception as exc:
            ready = False
            logger.error(f"Database: Error while attempting to connect to '{name}'")
            logger.error(exc)

    return ready


def caches_ready() -> bool:
    """Check health of cache connections.

    Calls get_stats() to connect to each memcached instance and get its stats.
    This can effectively check if each is online.
    """
    from django.core.cache import caches
    from django.core.cache.backends.memcached import BaseMemcachedCache

    ready = True

    for cache in caches.all():
        if not isinstance(cache, BaseMemcachedCache):
            continue

        try:
            stats = cache._cache.get_stats()
            if len(stats) != len(cache._servers):
                ready = False
                logger.error(f"Cache: Unable to get stats for '{cache}'")
        except Exception as exc:
            ready = False
            logger.error("Cache: Error while attempting to connect to '{cache}'")
            logger.error(exc)

    return ready


def check_readiness() -> HttpResponse:
    """Raise as exception if the server is not ready."""
    ready = True

    try:
        ready = databases_ready() and caches_ready()
    except ModuleNotFoundError as exc:
        logger.error("Import: Error while importing Django modules")
        logger.error(exc)
    except Exception as exc:
        logger.error("Unknown: Critical error")
        logger.error(exc)

    return HttpResponse("OK") if ready else HttpResponseServerError("Not Ready")


class HealthCheckMiddleware:
    """Simple Django health check endpoints.

    Endpoints:
    /healthz    Responds with 200 OK if server can return a simple response.
    /readiness  Responds with 200 OK if requisite databases and caches are ready.
    """

    endpoints = (
        HEALTHZ_ENDPOINT,
        READINESS_ENDPOINT,
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request) -> HttpResponse:
        if request.method != "GET" or request.path not in self.endpoints:
            # Passthrough if we aren't accessing health checks.
            return self.get_response(request)

        if request.path == "/readiness":
            # Throw an exception if checks don't pass.
            return check_readiness()

        # Return a simple 200 OK response.
        return HttpResponse("OK")
