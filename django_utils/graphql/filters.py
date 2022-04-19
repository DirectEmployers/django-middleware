from django.core.exceptions import ValidationError
from django.forms import MultipleChoiceField
from django_filters import MultipleChoiceFilter
from graphene_django.filter.filterset import (
    GlobalIDFilter,
    GlobalIDMultipleChoiceFilter,
)
from graphene_django.forms import GlobalIDFormField, GlobalIDMultipleChoiceField

from shared_library.graphql.errors import GraphQLError


class ErrorHandlingFilterField:
    """
    Adds an overwrite of the django form field method `clean` which catches
    ValidationErrors, and reraises them as GraphQL errors that can be handled by our
    GraphQL implementation. This prevents silent failures from invalid values.

    Extend the target form-field with this, and extend the target filter and replace
    it's `field_class` with the new form-field.
    """

    def clean(self, value):
        try:
            return super().clean(value)
        except ValidationError as e:
            if e.params:
                msg = e.message % e.params
            else:
                msg = e.message
            raise GraphQLError(msg) from e


class ErrorHandlingGlobalIDField(ErrorHandlingFilterField, GlobalIDFormField):
    pass


class ErrorHandlingMultipleChoiceField(ErrorHandlingFilterField, MultipleChoiceField):
    pass


class ErrorHandlingGlobalIDMultipleChoiceField(
    ErrorHandlingFilterField, GlobalIDMultipleChoiceField
):
    pass


class GlobalIDFilterWithErrors(GlobalIDFilter):
    field_class = ErrorHandlingGlobalIDField


class MultipleChoiceFilterWithErrors(MultipleChoiceFilter):
    field_class = ErrorHandlingMultipleChoiceField


class GlobalIDMultipleChoiceFilterWithErrors(GlobalIDMultipleChoiceFilter):
    field_class = ErrorHandlingGlobalIDMultipleChoiceField
