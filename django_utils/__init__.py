"""
Module for code that can be shared between services (micro and monolith).

`shared_library` is a package intended to be imported and reused throughout
multiple microservices. To maintain decoupled deployments, this means that every
module in `shared_library` must comply with the following constraints:

1. May not import code from any other DE code, outside of the `shared_library`
    directory.
2. May not directly interact with any databases or Django models. If data is
    required, the module should request it from the appropriate microservice API.
3. Modules must avoid depending on the de.works monolith in any way.
"""
