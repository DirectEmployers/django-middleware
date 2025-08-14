"""
Module for code that can be shared between Django services.

`django-middleware` is a package intended to be imported and reused throughout
multiple microservices. To maintain decoupled deployments, this means that every
module in `django-middleware` must comply with the following constraints:

1. May not import code from any other DE code, outside the `django-middleware` directory.
2. May not directly interact with any databases or Django models. If data is
    required, the module should request it from the appropriate microservice API.
3. Modules must avoid depending on the de.works monolith in any way!
"""
