"""
The secret parameters of a configuration.

A module declares a configuration parameter as a secret with ``secret=True`` in the metadata
of its ``Configuration`` field, next to ``description`` and ``required``. This app does not act
on that declaration, and deliberately so: it is the machine that holds the credential, it hands
the running configuration to its own editor through ``GET /configuration/current``, and it
reports that same configuration to every mothership it is paired with.

What is left is the reverse direction. The hub replaces the secrets of a *public* configuration
with :data:`config.SECRET_PLACEHOLDER` before anyone can read it, so a configuration downloaded
from there arrives with credentials that were never in it. :func:`placeholders` finds that
marker, which turns a confusing authentication failure at connect time into an error naming the
module and the parameter.
"""
# Internal imports.
import config


def placeholders(configuration_dict: list[dict]) -> list[tuple[str, str]]:
    """
    The parameters of a configuration whose value is still the placeholder of the hub.

    Matched on the value alone rather than on what the local module declares as a secret: the
    marker is only ever written by the hub over a value it removed, so it means the credential
    is missing whether or not this app happens to know the module that wanted it.

    :param configuration_dict: The configuration as a list of module configurations.

    :returns: One (module id, parameter) pair per missing credential.
    """
    found: list[tuple[str, str]] = []
    for module_config in configuration_dict or []:
        if not isinstance(module_config, dict):
            continue
        module_id = str(module_config.get("id", "-"))
        for key, value in module_config.items():
            if value == config.SECRET_PLACEHOLDER:
                found.append((module_id, str(key)))
    return found
