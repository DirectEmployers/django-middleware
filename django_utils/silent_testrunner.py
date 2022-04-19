import logging

from django.conf import settings
from django_jenkins.runner import CITestSuiteRunner


class SilentTestRunner(CITestSuiteRunner):
    def run_tests(self, test_labels=None, extra_tests=None, **kwargs):
        logging.disable(logging.CRITICAL)

        # Only run tests from settings.PROJECT_APPS unless overridden.
        if not test_labels:
            test_labels = settings.PROJECT_APPS

        return super(SilentTestRunner, self).run_tests(
            test_labels, extra_tests, **kwargs
        )
