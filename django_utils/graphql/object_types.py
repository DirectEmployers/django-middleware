"""Module for holding generally useful ObjectTypes."""

import graphene
from django.contrib.gis.geos.point import Point


class GeoDjangoPointInterface:
    """GraphQL interface for `django.contrib.gis.geos.point.Point`."""

    latitude = graphene.Float()
    longitude = graphene.Float()


class GeoDjangoPoint(GeoDjangoPointInterface, graphene.ObjectType):
    """GraphQL type for `django.contrib.gis.geos.point.Point`."""

    @classmethod
    def from_point(cls, point: Point):
        """
        Instantiate a `GeoDjangoPoint` from a `Point`.

        Made to be used in a resolver for a `PointField`.
        """
        return cls(latitude=point.y, longitude=point.x)


class GeoDjangoPointInput(GeoDjangoPointInterface, graphene.InputObjectType):
    """Input type for `django.contrib.gis.geos.point.Point`."""
