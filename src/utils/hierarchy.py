"""
The ISA-95 physical model hierarchy (unified namespace) this app sits in.

ISA-95 (IEC 62264) describes a plant as a strict containment hierarchy, and a unified
namespace is that hierarchy used as the address of every value the plant produces:

    Enterprise                      the organization - the hub username
      Site                          a plant or location
        Area                        a part of a site
          Work Center               a production line or cell
            Work Unit               a machine
              Equipment Module      a functional unit of that machine
                Control Module      the app itself - APP_DESCRIPTION

Only the two ends of it are known without being told: the enterprise is the hub account
this app authenticates as, and the control module is the app description, which already
falls back to the hostname. Everything between is the operator's knowledge of their own
plant and is read from the environment, like every other setting.

A level nobody filled in is *left out of the path* rather than filled with a placeholder.
That is what keeps the default path identical to what deployments have been publishing
all along - '<hub username>/<app description>' - so adding this feature moves nobody's
MQTT topics. Set the levels you have and the namespace grows downwards from the
enterprise; leave them empty and nothing changes. The cost is that the path has no fixed
depth, so a subscriber cannot address a level by position ('+/+/+/#') unless every app it
covers fills the same levels in - which is a good reason to fill them all in on a site
that wants to subscribe that way, and no reason to invent segments for one that does not.

The assembled path is published back into the environment as 'HIERARCHY_PATH', so a module
configuration can use it as a dynamic variable, e.g. as an MQTT topic:

    ${env.HIERARCHY_PATH}/${local.measurement}

It is *derived*, so it is deliberately not part of 'data_layer.settings': it is not the
operator's to edit, and writing it there would persist it into the settings file and
offer it as a field in the user interface. It is recomputed by 'refresh', which the
initialization calls after the settings file is read, after the hub username arrives
(which can be minutes later on a machine that boots before its network is up) and after
the settings are changed through the api.
"""
from typing import NamedTuple
import logging
import os

# Internal imports.
import config

logger = logging.getLogger(config.APP_NAME.lower() + '.' + __name__)
"""The logger instance."""

SEPARATOR: str = "/"
"""What joins two levels. A slash, because the path is meant to be usable as an MQTT topic."""

FORBIDDEN_CHARACTERS: str = "/+#"
"""
Characters a single level may not contain.

The separator itself, plus the two MQTT wildcards. A work center called 'Line 1/2' would
otherwise silently become two levels, and a '+' or '#' in a topic filter matches whole
branches the publisher never meant. They are replaced by '-' rather than rejected: this
runs at start-up on a value nobody is watching being validated, and a slightly renamed
level is a much better outcome than an app that refuses to start.
"""


class Level(NamedTuple):
    """
    One level of the hierarchy.
    """
    name: str
    """The ISA-95 name of the level."""
    variable: str
    """The environment variable holding the value."""


LEVELS: tuple[Level, ...] = (
    Level("Enterprise", "ENTERPRISE"),
    Level("Site", "SITE"),
    Level("Area", "AREA"),
    Level("Work Center", "WORK_CENTER"),
    Level("Work Unit", "WORK_UNIT"),
    Level("Equipment Module", "EQUIPMENT_MODULE"),
    Level("Control Module", "APP_DESCRIPTION"),
)
"""
The levels, top down.

The app description has always been the name of this particular app among its siblings, 
which is exactly what the control module level means, and it is what the hub stores, what the
fleet list shows and what the existing MQTT topics are built from. A second name for it
would have been a second source of truth.
"""

ENTERPRISE: Level = LEVELS[0]
"""The root of the hierarchy. Resolved from the hub account when it is not set explicitly."""


def sanitize(value: str | None) -> str:
    """
    One level's value, safe to put in a path.

    :param value: The value as configured, if there is one.
    :return: The value without surrounding whitespace and without path or wildcard
             characters, or "" if there was nothing to begin with.
    """
    if not value:
        return ""
    value = str(value).strip()
    for character in FORBIDDEN_CHARACTERS:
        value = value.replace(character, "-")
    return value.strip()


def enterprise() -> str:
    """
    The enterprise level.

    'ENTERPRISE' if it is set, and otherwise the hub account this app authenticates
    as. The override exists for an app that does not report to the hub at all: it still
    belongs to an enterprise, it just has nowhere to learn the name from.

    :return: The enterprise, or "" if this app has no hub account yet and none was given.
    """
    return sanitize(os.environ.get(ENTERPRISE.variable) or os.environ.get("HUB_USERNAME"))


def levels() -> dict[str, str]:
    """
    Every level and its current value, top down.

    :return: The level name mapped to its value, "" for a level that is not set.
    """
    resolved = {ENTERPRISE.name: enterprise()}
    for level in LEVELS[1:]:
        resolved[level.name] = sanitize(os.environ.get(level.variable))
    return resolved


def reported() -> dict[str, str]:
    """
    The levels a mothership is told about, under the names it stores them by.

    The two ends of the hierarchy are left out on purpose. The control module is the app
    description, which is already part of every report. And the enterprise is the account
    the report authenticates as, which the receiving side knows for certain and this side
    only believes - so it is derived there rather than taken from here, and an app cannot
    file itself under somebody else's enterprise by setting an environment variable.

    :return: The middle levels, keyed as the api names them. A level that is not set is
             sent as "" rather than left out, so clearing one here clears it there.
    """
    return {level.variable.lower(): sanitize(os.environ.get(level.variable))
            for level in LEVELS[1:-1]}


def path() -> str:
    """
    The unified namespace path of this app.

    The levels that have a value, joined by 'SEPARATOR'. Empty when the enterprise is
    unknown: it is the root of the hierarchy, and a path that starts at the site belongs
    to nobody in particular. On the managed broker it would also be a topic the access
    control rejects, because a topic has to start with the account publishing it -
    failing to build the path at all is the more honest version of that.

    :return: The path, or "" if the enterprise level could not be resolved.
    """
    resolved = levels()
    if not resolved[ENTERPRISE.name]:
        return ""
    return SEPARATOR.join(value for value in resolved.values() if value)


def refresh() -> str:
    """
    Recompute the path and publish it as 'HIERARCHY_PATH'.

    Called whenever something it is built from can have changed. The variable is removed
    rather than set to "" when the path cannot be built, so '${env.HIERARCHY_PATH}' fails
    loudly with "could not find key" instead of quietly resolving to a topic that starts
    with a slash.

    :return: The path, or "" if it could not be built.
    """
    current = path()
    previous = os.environ.get("HIERARCHY_PATH")
    if current:
        os.environ["HIERARCHY_PATH"] = current
    else:
        os.environ.pop("HIERARCHY_PATH", None)

    if current != previous:
        if current:
            logger.info("Unified namespace (ISA-95) of this app: {0}".format(current))
        elif previous:
            logger.warning("The unified namespace (ISA-95) path of this app is no longer resolvable.")
        else:
            logger.info("Could not determine the unified namespace (ISA-95) path of this app, "
                        "the enterprise level is unknown. It is taken from your hub account, or "
                        "from '{0}' if this app does not report to the hub."
                        .format(ENTERPRISE.variable))
    return current
