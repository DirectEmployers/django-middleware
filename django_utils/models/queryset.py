"""Code for augmenting Django QuerySets."""
from typing import Any, Dict, Tuple, Type, TypeVar

from django.db import models

Model = TypeVar("Model", bound=models.Model)


def create_and_clean(model_class: Type[Model], **kwargs: Any) -> Model:
    """
    Instantiate a model, clean it, save it, return it.
    """
    model = model_class(**kwargs)
    model.full_clean()
    model.save()
    return model


def get_or_create_and_clean(
    model_class: Type[Model], defaults: Dict[str, Any] = {}, **kwargs: Any
) -> Tuple[Model, bool]:
    """
    Like `get_or_create()`, but calls the `full_clean()` method on the new object
    *before* saving it to the database.

    See the Django docs on `get_or_create()` for more details:
    https://docs.djangoproject.com/en/dev/ref/models/querysets/#get-or-create

    Raises `ValidationError` if `full_clean()` finds problems.
    """
    created = False
    model: Model
    try:
        model = model_class.objects.get(**kwargs)
    except model_class.DoesNotExist:
        model = model_class(**{**kwargs, **defaults})
        model.full_clean()
        model.save()
        created = True
    return (model, created)
