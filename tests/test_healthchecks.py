from unittest import mock, TestCase

from django.conf import settings
from django.db import connection, DatabaseError
from django.http.request import HttpRequest

from django_middleware.healthchecks import HealthCheckMiddleware
from tests.django import django_settings

settings.configure(django_settings, DEBUG=True)


def call_middleware(endpoint):
    hcm = HealthCheckMiddleware(lambda x: x)
    request = HttpRequest()
    request.method = "GET"
    request.path = endpoint
    return hcm(request)


class HealthzTests(TestCase):
    def test_healthz_endpoint(self):
        response = call_middleware("/healthz")
        self.assertEqual(response.status_code, 200)


class ReadinessTests(TestCase):
    def test_readiness_endpoint(self):
        response = call_middleware("/readiness")
        self.assertEqual(response.status_code, 200)

    @mock.patch.object(connection, "cursor", side_effect=DatabaseError)
    def test_readiness_errors(self, mock):
        with self.assertLogs("django.server"):
            response = call_middleware("/readiness")
            self.assertEqual(response.status_code, 500)
