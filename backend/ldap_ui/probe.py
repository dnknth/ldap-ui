"LDAP connectivity and configuration probe (`/api/probe`)."

import ldap3
from fastapi import HTTPException
from ldap3.core.exceptions import (
    LDAPException,
    LDAPInvalidCredentialsResult,
)

from . import settings
from .entities import Diagnostic, ProbeResult
from .ldap_connection import get_schema, ldap_connect
from .ldap_helpers import unique

# Default search filter
ANY = "(objectClass=*)"


async def run_probe() -> ProbeResult:
    """
    Probe the LDAP directory connectivity and configuration.

    A full probe mirrors what every real request does: open an anonymous
    connection, resolve the base DN and schema, and sanity-check the settings.
    Returns a ProbeResult whose `ok` is true when the directory is usable, and
    whose `diagnostics` list carries individual findings (severity,
    message) for misconfigurations worth surfacing to the operator.
    """
    diagnostics: list[Diagnostic] = []
    try:
        async with ldap_connect() as connection:
            # Base DN present and readable? A stale/wrong BASE_DN makes the
            # whole tree 404 while the connection itself succeeds.
            # (`ldap_connect` resolves it best-effort; ambiguous directories
            # leave it unset, which is diagnosed here.)
            if not settings.BASE_DN:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        message="Could not detect the directory's base entry. "
                        "Provide the BASE_DN setting.",
                    )
                )
            else:
                try:
                    await unique(
                        connection,
                        connection.search(
                            settings.BASE_DN,
                            search_filter=ANY,
                            search_scope=ldap3.BASE,
                            get_operational_attributes=True,
                        ),
                    )
                except (HTTPException, LDAPException):
                    if settings.config("BASE_DN", default=None):
                        message = (
                            "The configured base entry does not exist or "
                            "cannot be read. Check the BASE_DN setting."
                        )
                    else:
                        message = (
                            "The auto-detected base entry could not be read. "
                            "Provide the BASE_DN setting."
                        )
                    diagnostics.append(Diagnostic(severity="error", message=message))

            # Schema readable? A missing/unreadable schema breaks /schema for
            # every user.
            if not settings.SCHEMA_DN:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        message="Could not detect the directory's schema. "
                        "Provide the SCHEMA_DN setting.",
                    )
                )
            else:
                try:
                    await get_schema(connection)
                except (HTTPException, LDAPException):
                    if settings.config("SCHEMA_DN", default=None):
                        message = (
                            "The configured schema could not be read. "
                            "Check the SCHEMA_DN setting."
                        )
                    else:
                        message = (
                            "The auto-detected schema could not be read. "
                            "Provide the SCHEMA_DN setting."
                        )
                    diagnostics.append(Diagnostic(severity="error", message=message))
    except LDAPInvalidCredentialsResult:
        # Directory reachable but rejects anonymous binds. That breaks the
        # anonymous user search used to resolve the login DN (only avoidable
        # with BIND_PATTERN) and the root-DSE auto-detection of base/schema.
        # Each feature that cannot be satisfied is diagnosed separately.
        bind_pattern = settings.config("BIND_PATTERN", default=None)
        if bind_pattern is None:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    message="The directory rejects anonymous binds, but "
                    "login needs an anonymous search to resolve user names. "
                    "Configure BIND_PATTERN or allow anonymous access.",
                )
            )
        if not settings.BASE_DN:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    message="Could not detect the directory's base entry, "
                    "and anonymous access is denied. Provide the BASE_DN "
                    "setting.",
                )
            )
        if not settings.SCHEMA_DN:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    message="Could not detect the directory's schema, and "
                    "anonymous access is denied. Provide the SCHEMA_DN "
                    "setting.",
                )
            )
    except (LDAPException, ValueError) as exc:
        msg = "Cannot connect to the LDAP directory. Check LDAP_URL."
        if "tls" in type(exc).__name__.lower() or "tls" in str(exc).lower():
            msg = (
                "The TLS connection to the LDAP directory failed. "
                "Check the certificate and TLS settings."
            )
        diagnostics.append(Diagnostic(severity="error", message=msg))

    # Config sanity checks that don't need the directory.
    if settings.INSECURE_TLS:
        diagnostics.append(
            Diagnostic(
                severity="warning",
                message="TLS certificate checking is disabled. Connections "
                "are not safely verified.",
            )
        )

    bind_pattern = settings.config("BIND_PATTERN", default=None)
    if bind_pattern is not None and bind_pattern.count("%s") != 1:
        diagnostics.append(
            Diagnostic(
                severity="error",
                message="The BIND_PATTERN setting is malformed: it needs "
                "exactly one %s placeholder.",
            )
        )

    # Usable (not merely reachable): any error diagnostic makes the deployment not ok.
    return ProbeResult(
        ok=not any(d.severity == "error" for d in diagnostics),
        diagnostics=diagnostics,
    )
