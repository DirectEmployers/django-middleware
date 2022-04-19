"""DirectEmployer's custom Graphene Relay code."""
from functools import wraps
from inspect import cleandoc
from typing import Type, TypeVar

from django import forms
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models.constants import LOOKUP_SEP
from graphene import Connection, Int, JSONString, List, NonNull, ResolveInfo, String
from graphene.utils.str_converters import to_camel_case, to_snake_case
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from django_filters.filters import Filter
from graphql_relay.connection.arrayconnection import offset_to_cursor
from graphql_relay.node.node import from_global_id

from django_utils.graphql.errors import GraphQLError


class ScopeError(PermissionDenied):
    """Indicates that a grant is not supported."""

    pass


class IntegerFilter(Filter):
    """
    Custom django_filter. django_filters.NumberFilter appears in the GraphiQL schema as
    a Float, instead of an Int.
    """

    field_class = forms.IntegerField


class CustomConnection(Connection):
    """
    Custom Connection with support for total_count (totalCount)
    by exposing the `length` field of a Connection
    """

    class Meta:
        abstract = True

    total_count = NonNull(Int)

    def resolve_total_count(self, info, **kwargs):
        # no performance penalty: called only when total_count is requested
        return self.length


class DEDjangoObjectType(DjangoObjectType):
    class Meta:
        abstract = True

    @classmethod
    def get_node(cls, info, id):
        raise ScopeError("Permission Denied")

    @classmethod
    def __init_subclass_with_meta__(cls, **options):
        """
        Overwrite the provided connection with our CustomConnection, and add a description.
        """
        # Setup the connection and its class
        connection_class = CustomConnection
        connection = connection_class.create_type(
            "{}Connection".format(cls.__name__), node=cls
        )

        # Update the arguments
        options["connection_class"] = connection_class
        options["connection"] = connection

        # Add a description if it wasn't already included.
        if "description" not in options and not cls.__doc__:
            options["description"] = cleandoc(options["model"].__doc__)

        # Call the parent method
        super().__init_subclass_with_meta__(**options)


class DEDjangoConnectionField(DjangoFilterConnectionField):
    """
    Add 3 default connection arguments: `sort`, `filters`, and `jump_to_page`.

    Even though `order_by` is already an argument, it doesn't appear in the
    Graphene code. To accommodate for the missing implementation without
    breaking in the future, "sort" is intentionally chosen, and defined as a
    list, to support ordering by multiple fields. Sorting will be available by
    default when using this custom connection.

    GraphQL usage:
    provide "sort" just like "first", "last", "before" etc.

    `sort: "abc"` - will order nodes by field "abc" of the model.

    `sort: ["abc", "-xyz"]` - will order nodes by "abc" ASC then "xyz" DESC.


    `filters` provides a way to specify filtering dynamically without having to
    use the top-level filtering arguments:

    Example:

    ```graphql
    {
        getData(
            first: 10,
            name_Icontains: "bob",
            enabled: true
        )
    }
    ```

    Can be replaced by
    ```graphql
    {
        getData(
            first: 10,
            filters: "{\"name_Icontains\": \"bob\", \"enabled\": true}"
        )
    }
    ```


    `jump_to_page` provides an simple mechanism to jump to an arbitrary page of
    data (1-indexed), given a value for `first`.
    """

    def __init__(
        self,
        type,
        fields=None,
        order_by=None,
        extra_filter_meta=None,
        filterset_class=None,
        *args,
        **kwargs,
    ):
        # Define defaults for our new arguments
        kwargs.setdefault(
            "sort",
            List(
                String,
                description=(
                    "Order the results by one or more fields. "
                    'Prefix field name with "`-`" to sort descending.'
                ),
            ),
        )
        kwargs.setdefault(
            "filters",
            JSONString(
                description="Object containing filter arguments for querying the results."
            ),
        )
        kwargs.setdefault(
            "jump_to_page",
            Int(
                description=(
                    "The index (1-based) of the page to display. "
                    "Page size is defined by `first`."
                )
            ),
        )

        super(DEDjangoConnectionField, self).__init__(
            type, fields, order_by, extra_filter_meta, filterset_class, *args, **kwargs
        )

    @classmethod
    def resolve_queryset(
        cls, connection, iterable, info, args, filtering_args, filterset_class
    ):
        """Ensure that arguments in `filters` are included when filtering."""
        # Put the contents of `args['filters']` into `filtering_args`.
        filtering_args = cls.extract_filter_kwargs(args, filtering_args)

        # Put the content of `filtering_args` into `args`, so that the parent
        # method will include them when building the `FilterSet` instance for
        # this connection.
        args = {**args, **filtering_args}

        # Pass the modified arguments to the parent method.
        return super().resolve_queryset(
            connection, iterable, info, args, filtering_args, filterset_class
        )

    @classmethod
    def connection_resolver(
        cls,
        resolver,
        connection,
        default_manager,
        queryset_resolver,
        max_limit,
        enforce_first_or_last,
        root,
        info,
        **args,
    ):
        """Implement logic for `jump_to_page` and `sort`."""
        jump_to_page = args.get("jump_to_page")
        first = args.get("first")
        last = args.get("last")
        order = args.get("sort")

        if jump_to_page:
            if not (first or last):
                raise GraphQLError(
                    (
                        "You must provide a `first` or `last` value to properly "
                        "paginate the `{}` connection."
                    ).format(info.field_name)
                )

            page_size = first or last
            if page_size:
                offset = page_size * (int(jump_to_page) - 1) - 1
                args["after"] = offset_to_cursor(offset)

        if order:
            order = [to_snake_case(o) for o in order]
            default_manager = default_manager.order_by(*order)

            def new_resolver(original_resolver):
                """
                Return a new resolver that always applies the ordering.

                This is needed because if a resolver is defined for a field,
                `default_manager` won't be used and the ordering will be lost.

                See: `graphene_django.fields.DjangoConnectionField.connection_resolver`
                for details.
                """

                @wraps(original_resolver)
                def wrapped(*args, **kwargs):
                    queryset = original_resolver(*args, **kwargs)
                    if queryset is None:
                        return default_manager
                    return queryset.order_by(*order)

                return wrapped

            # Make sure the resolver returns a sorted iterable
            resolver = new_resolver(resolver)

        return super().connection_resolver(
            resolver,
            connection,
            default_manager,
            queryset_resolver,
            max_limit,
            enforce_first_or_last,
            root,
            info,
            **args,
        )

    @staticmethod
    def convert_field_lookup(field_lookup: str) -> str:
        """
        Convert a camel-cased filter argument to a Django field lookup.

        Examples:
        >>> convert_field_lookup('reportName_Icontains')
        'report_name__icontains'
        >>> convert_field_lookup('prefab')
        'prefab'
        >>> convert_field_lookup('partner_OutreachTags')
        'partner__outreach_tags
        """
        lookups = models.Field.get_lookups().keys()
        incoming_lookups = [lookup.capitalize() for lookup in lookups]

        split = field_lookup.rsplit("_", maxsplit=1)
        if len(split) == 1:
            # No "_", assume it's an exact filter and snake it.
            snake_lookup = to_snake_case(field_lookup)
            return snake_lookup

        # Check if the string ends in a lookup
        head, tail = split
        if tail in incoming_lookups:
            # If it does, snake separately and join with "__"
            snake_head = to_snake_case(head)
            snake_tail = to_snake_case(tail)
            return LOOKUP_SEP.join([snake_head, snake_tail])
        else:
            # If it doesn't, assume it's an exact filter and snake it.
            snake_lookup = to_snake_case(field_lookup)
            return snake_lookup

    @classmethod
    def extract_filter_kwargs(cls, kwargs: dict, filtering_args: dict):
        """
        Extract any filters kwargs out of the "filters" dictionary
        if it was provided by the front end, otherwise extract them
        as we normally would and only return the filters that have
        been defined on filtering_args.

        :param kwargs dict
        :param filtering_args dict
        :return dict

        """

        if "filters" in kwargs:
            dynamic_filters = {}

            for field_lookup, lookup_value in kwargs["filters"].items():
                # convert the camel cased argument to a django field lookup case.
                django_field_lookup = cls.convert_field_lookup(field_lookup)
                if django_field_lookup not in filtering_args:
                    raise GraphQLError(
                        (
                            "Invalid filter field lookup '{original}' "
                            "(parsed to '{field}') "
                            "encountered. Valid field lookups are: {lookups}"
                        ).format(
                            field=django_field_lookup,
                            original=field_lookup,
                            lookups=", ".join(
                                to_camel_case(key) for key in filtering_args.keys()
                            ),
                        )
                    )

                dynamic_filters[django_field_lookup] = lookup_value

            return dynamic_filters

        filter_kwargs = {}

        for k, v in kwargs.items():
            if k in filtering_args:
                filter_kwargs[k] = v

        return filter_kwargs


def _resolve_reference(
    self: DjangoObjectType, info: ResolveInfo, **kwargs
) -> models.Model:
    """Translate a Relay node to a Django model instance."""
    model_id = int(from_global_id(self.id)[1])
    return self.get_node(info, model_id)


DjangoObjectType_ = TypeVar("DjangoObjectType_", bound=DjangoObjectType)


def add_resolve_reference(klass: Type[DjangoObjectType_]) -> Type[DjangoObjectType_]:
    """
    Add a private `__resolve_reference` method to the decorated class.

    Make `graphene.relay.Node` interfaces compatible with `graphene-federation`.
    """
    method_name = "_{}__resolve_reference".format(klass.__name__)
    setattr(klass, method_name, _resolve_reference)

    return klass
