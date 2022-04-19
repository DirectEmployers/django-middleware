"""Test the contents of `django_utils/graphql/object_types.py`."""

from django.contrib.gis.geos.point import Point
from django.test import SimpleTestCase

from django_utils.graphql import object_types


class TestGeoDjangoPoint(SimpleTestCase):
    """Test the behavior of the `GeoDjangoPoint` `ObjectType`."""

    def test_from_point(self):
        """Test that a `GeoDjangoPoint` can be created from a `Point`."""
        point = Point(x=1, y=2)
        graphene_point = object_types.GeoDjangoPoint.from_point(point)

        self.assertIsInstance(graphene_point, object_types.GeoDjangoPoint)
        self.assertEqual(graphene_point.longitude, point.x)
        self.assertEqual(graphene_point.latitude, point.y)
