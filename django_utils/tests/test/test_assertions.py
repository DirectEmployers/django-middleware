from shared_library.test.assertions import assert_function_registered_as_signal

from django.db.models import Model
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.test import SimpleTestCase


class TestModel(Model):
    pass


@receiver(post_save, sender=TestModel)
def post_save_func():
    pass


class AssertFunctionRegisteredAsSignalTestCase(SimpleTestCase):
    """
    Verify that checking a given function's registration status in a given
    signal works properly.
    """

    def test_assertion_passes_when_registered(self):
        assert_function_registered_as_signal(post_save_func, TestModel, post_save)

    def test_assertion_fails_when_not_registered(self):
        with self.assertRaises(AssertionError):
            assert_function_registered_as_signal(post_save_func, TestModel, m2m_changed)
