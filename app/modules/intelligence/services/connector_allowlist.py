"""Fail-closed allowlist gate for connector types reaching the crosswalk write path.

The crosswalk resolves an external identity (a ServiceNow sys_id, a Jira key,
a device object from an AD/M365 sync, ...) to an internal element. That write
is the point where a connected system's data enters the model, so it is also
the point where a source with no recorded lawful basis for the data it
carries (HR systems, security/SIEM tooling, arbitrary "mystery" sources
nobody has reviewed) must be refused rather than silently accepted.

The mechanism is an allowlist, not a denylist: an unrecognised connector
type is refused by default, because the failure mode of a denylist here is
"a new source ships and nobody remembers to add it to the block list", which
is exactly backwards for data that may carry personal or security
information. Only a source that is either hard-coded below or explicitly
approved via configuration is permitted through.

This module ships ahead of the crosswalk write path it guards. There is no
crosswalk table or writer yet, so `assert_connector_permitted` currently has
no caller in this codebase -- it exists now so that when the crosswalk
writer is built, the gate is already in place rather than being retrofitted
onto a write path that has already shipped without it. See
`scripts/check_crosswalk_writer_gated.py`, which fails the build the day a
crosswalk writer appears without a call to this function on its path.

This module claims exactly one boundary: the crosswalk write. It does not
gate, and must not be read as gating, how a connector is *configured*
(credentials, endpoint URLs, etc. accepted at connector-setup time) -- that
is a separate, currently unfenced, surface tracked outside this module.
"""

from __future__ import annotations

import logging

from flask import current_app, g

logger = logging.getLogger("archie.intelligence.connector_allowlist")

# Sources with a recorded, reviewed basis for the data they carry, permitted
# without any additional configuration:
#   - servicenow, jira, m365, devops, lucidchart: architecture/ITSM tooling
#     already in use, none of it carrying HR or security-sensitive payloads
#     by itself.
#   - ea_tool: architecture-tool exports (models, viewpoints, capability
#     maps). It is already configurable today with no gate in front of it at
#     all, and it carries architecture metadata, not personal, HR or
#     security data -- so adding a gate here would restrict something that
#     was never restricted, for data that isn't the concern this gate exists
#     to address.
PERMITTED_CONNECTOR_TYPES = frozenset(
    {"servicenow", "jira", "m365", "devops", "lucidchart", "ea_tool"}
)

# Sources known to require a compliance review before they can be connected
# (they carry HR, personal or security data), used only to produce a
# specific, actionable refusal message naming the missing artifact. This set
# is never consulted to decide whether to refuse a connector -- everything
# not in PERMITTED_CONNECTOR_TYPES (unioned with the config-approved set) is
# refused regardless of whether it appears here or not. Its only job is
# making the refusal message for a *known* pending source more useful than
# "not permitted".
GATED_CONNECTOR_TYPES = frozenset({"hr", "hris", "siem", "identity_provider"})


class ConnectorNotPermitted(PermissionError):
    """Raised when a connector type is not on the effective allowlist.

    Carries a human-readable reason naming the missing compliance artifact
    when the type is a recognised pending source, or stating plainly that
    the type is unrecognised otherwise.
    """


def _effective_allowlist() -> frozenset:
    """The permitted set plus whatever has been approved via configuration.

    `COMPLIANCE_APPROVED_CONNECTOR_TYPES` defaults to an empty tuple, so the
    default behaviour is closed: nothing is approved until a specific
    connector type is added to this configuration key, which should only
    happen once a compliance reviewer has signed off on that source's
    lawful basis for the data it carries and on the hosting implications of
    running it under this project's AGPL terms.
    """
    approved = current_app.config.get("COMPLIANCE_APPROVED_CONNECTOR_TYPES", ())
    return PERMITTED_CONNECTOR_TYPES | frozenset(approved)


def assert_connector_permitted(connector_type: str) -> None:
    """Raise ``ConnectorNotPermitted`` unless *connector_type* is allowed.

    Call this before any crosswalk write for the given connector type. Does
    nothing (returns normally) when the type is permitted; every other case
    is refused, logged at WARNING with the connector type and the current
    organisation, and surfaced to the caller via the ``feed_not_connected``
    reason code.
    """
    if connector_type in _effective_allowlist():
        return

    org_id = getattr(g, "current_org_id", None)

    if connector_type in GATED_CONNECTOR_TYPES:
        reason = (
            f"connector type {connector_type!r} requires a compliance "
            "sign-off artifact approving its lawful basis and AGPL hosting "
            "implications before it can be connected; none is on file"
        )
    else:
        reason = f"connector type {connector_type!r} is not on the permitted allowlist"

    logger.warning(
        "connector %r refused for organisation %r: %s",
        connector_type, org_id, reason,
    )

    error = ConnectorNotPermitted(reason)
    error.reason_code = "feed_not_connected"
    error.connector_type = connector_type
    raise error


__all__ = [
    "PERMITTED_CONNECTOR_TYPES",
    "GATED_CONNECTOR_TYPES",
    "ConnectorNotPermitted",
    "assert_connector_permitted",
]
