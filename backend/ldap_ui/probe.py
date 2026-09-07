"LDAP connectivity and configuration probe (`/api/probe`)."

import ldap3
from fastapi import HTTPException
from ldap3.core.exceptions import (
    LDAPException,
    LDAPInappropriateAuthenticationResult,
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

    A full probe opens an anonymous connection, resolves the base DN and
    schema, and sanity-checks the settings. When BIND_AS_USER is enabled,
    authenticated requests instead open their initial connection with the
    login user's credentials.
    """
    diagnostics: list[Diagnostic] = []
    try:
        async with ldap_connect() as connection:
            # Base DN present and readable? A stale/wrong BASE_DN makes the
            # whole tree 404 while the connection itself succeeds.
            # (`ldap_connect` resolves it best-effort; ambiguous directories
            # leave it unset, which is diagnosed here.)
            # In BIND_AS_USER mode these access checks with the probe's
            # anonymous connection would produce false errors on directories
            # that allow only anonymous root-DSE access. Authenticated
            # requests perform them with the login user's credentials.
            if not settings.BIND_AS_USER and not settings.BASE_DN:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        message="Could not detect the directory's base entry. "
                        "Provide the BASE_DN setting.",
                    )
                )
            elif not settings.BIND_AS_USER and settings.BASE_DN:
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
            if not settings.BIND_AS_USER and not settings.SCHEMA_DN:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        message="Could not detect the directory's schema. "
                        "Provide the SCHEMA_DN setting.",
                    )
                )
            elif not settings.BIND_AS_USER and settings.SCHEMA_DN:
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
    except (LDAPInappropriateAuthenticationResult, LDAPInvalidCredentialsResult):
        # The probe has no login credentials, so this failure is expected
        # when user-bound mode is correctly configured. Real requests derive
        # the user's DN from BIND_PATTERN and bind directly with the submitted
        # password instead of taking this anonymous path.
        bind_pattern = settings.config("BIND_PATTERN", default=None)
        if not (settings.BIND_AS_USER and bind_pattern is not None):
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    message="The directory rejects anonymous binds. Configure "
                    "BIND_AS_USER with BIND_PATTERN, or allow anonymous access.",
                )
            )
        if not settings.BIND_AS_USER and not settings.BASE_DN:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    message="Could not detect the directory's base entry, "
                    "and anonymous access is denied. Provide the BASE_DN "
                    "setting.",
                )
            )
        if not settings.BIND_AS_USER and not settings.SCHEMA_DN:
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
    if settings.BIND_AS_USER and bind_pattern is None:
        diagnostics.append(
            Diagnostic(
                severity="error",
                message="BIND_AS_USER requires BIND_PATTERN so the login "
                "user's DN can be resolved before connecting.",
            )
        )
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
