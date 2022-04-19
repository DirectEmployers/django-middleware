"""Code for using GraphQL Relay (https://relay.dev/)"""
from django.core.exceptions import ValidationError
from graphql_relay.node.node import from_global_id

from .errors import ERROR_VALIDATION


def id_or_raise(global_id: str, field_name: str) -> int:
    """
    If anything goes wrong with decoding `global_id`, raise `ValidationError`.

    `field_name` determines the name of the field in the resulting `ValidationError`.
    """
    try:
        return int(from_global_id(global_id)[1])
    except Exception as err:
        error_dict = {}
        error_dict[field_name] = [
            ValidationError(
                "Invalid global ID '%(id)s'",
                code=ERROR_VALIDATION,
                params={"id": global_id},
            )
        ]
        raise ValidationError(error_dict) from err
