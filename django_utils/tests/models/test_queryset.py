"""Tests for code in `django_utils/models/queryset.py`"""
from django.core.exceptions import ValidationError
from django.db import models
from django.test import TestCase

from django_utils.models import queryset


class TestModel(models.Model):
    foo = models.CharField(max_length=3)
    bar = models.IntegerField(null=True, blank=True)


class TestCreateAndClean(TestCase):
    """Test the behavior of `create_and_clean`."""

    databases = {"default"}

    def test_create(self):
        """Test that the model is created and saved."""
        result = queryset.create_and_clean(TestModel, foo="abc")
        self.assertIsInstance(result, TestModel)
        self.assertIsNotNone(result.pk)

    def test_clean(self):
        """Test that the model is validated before saving."""
        with self.assertRaises(ValidationError):
            queryset.create_and_clean(TestModel)


class TestGetOrCreateAndClean(TestCase):
    """Test the behavior of `get_or_create_and_clean`."""

    databases = {"default"}

    def test_get(self):
        """Test that if an object already exists with attributes, it is returned."""
        fields = {"foo": "abc", "bar": 1}
        obj: TestModel = TestModel.objects.create(**fields)
        returned_obj, created = queryset.get_or_create_and_clean(TestModel, **fields)
        self.assertFalse(created)
        self.assertEqual(returned_obj, obj)

    def test_create(self):
        """
        Test that if there is no match, make a new object and save it.
        """
        result, created = queryset.get_or_create_and_clean(
            TestModel, defaults={"foo": "abc"}, bar=2
        )
        self.assertTrue(created)
        self.assertIsInstance(result, TestModel)
        self.assertIsNotNone(result.pk)
        self.assertEqual(result.foo, "abc")
        self.assertEqual(result.bar, 2)

    def test_clean(self):
        """Test that the model is cleaned before saving."""
        with self.assertRaises(ValidationError):
            queryset.get_or_create_and_clean(TestModel, bar=2)
