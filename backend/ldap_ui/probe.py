"LDAP connectivity and configuration probe (`/api/probe`)."

from time import monotonic

import ldap3
from fastapi import HTTPException
from ldap3.core.exceptions import (
    LDAPException,
    LDAPInappropriateAuthenticationResult,
    LDAPInsufficientAccessRightsResult,
    LDAPInvalidCredentialsResult,
)

from . import settings
from .entities import Diagnostic, ProbeResult
from .ldap_connection import get_schema, ldap_connect
from .ldap_helpers import unique

# Default search filter
ANY = "(objectClass=*)"

# Failures the anonymous probe connection can hit when the directory restricts
# anonymous access to the root DSE. In BIND_AS_USER mode these are expected —
# real requests bind as the login user — so they are skipped rather than
# reported as configuration errors.
ANONYMOUS_ACCESS_ERRORS = (
    LDAPInappropriateAuthenticationResult,
    LDAPInvalidCredentialsResult,
    LDAPInsufficientAccessRightsResult,
)

# /api/probe serves a cached probe result so it never re-probes per client.
# The cache is refreshed at backend startup and again at most every PROBE_TTL
# seconds, so a directory that comes up after the backend does is picked up on
# refresh rather than wedging the frontend on a stale startup failure.
PROBE_TTL = 300  # seconds

_startup_probe: ProbeResult | None = None
_startup_probe_at: float = 0.0  # monotonic() time of the last cached probe


async def run_startup_probe() -> ProbeResult:
    "Run the probe and cache the result (startup and on TTL expiry)."
    global _startup_probe, _startup_probe_at
    _startup_probe = await run_probe()
    _startup_probe_at = monotonic()
    return _startup_probe


def startup_probe() -> ProbeResult | None:
    "Cached probe result if still fresh, else None (stale or not yet run)."
    if _startup_probe is None:
        return None
    if monotonic() - _startup_probe_at > PROBE_TTL:
        return None
    return _startup_probe


async def run_probe() -> ProbeResult:
    """
    Probe the LDAP directory connectivity and configuration.

    A full probe opens an anonymous connection, resolves the base DN and
    schema, and sanity-checks the settings. When BIND_AS_USER is enabled,
    authenticated requests instead open their initial connection with the
    login user's credentials; the probe still runs its base/schema checks on
    the anonymous connection, skipping failures caused purely by anonymous
    access being denied. Returns a ProbeResult whose `ok` is true when the
    directory is usable, and whose `diagnostics` list carries individual
    findings (severity, message) for misconfigurations worth surfacing to the
    operator.
    """
    diagnostics: list[Diagnostic] = []
    try:
        async with ldap_connect() as connection:
            # Base DN present and readable? A stale/wrong BASE_DN makes the
            # whole tree 404 while the connection itself succeeds.
            # (`ldap_connect` resolves it best-effort; ambiguous directories
            # leave it unset, which is diagnosed here.)
            #
            # The probe always connects anonymously. In BIND_AS_USER mode the
            # real requests bind as the login user, so a directory that grants
            # anonymous access only to the root DSE makes the checks below
            # fail for a reason unrelated to those requests. Such anonymous
            # permission failures are skipped; anything else (a wrong BASE_DN,
            # an unreadable schema, ...) is a real misconfiguration and is
            # reported regardless of bind mode.
            if not settings.BASE_DN:
                if settings.BIND_AS_USER:
                    diagnostics.append(
                        Diagnostic(
                            severity="warning",
                            message="BIND_AS_USER mode: the base entry could "
                            "not be detected. Searches resolve it from the "
                            "BASE_DN setting; consider setting it explicitly.",
                        )
                    )
                else:
                    diagnostics.append(
                        Diagnostic(
                            severity="error",
                            message="Could not detect the directory's base "
                            "entry. Provide the BASE_DN setting.",
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
                except (HTTPException, LDAPException) as exc:
                    if settings.BIND_AS_USER and isinstance(
                        exc, ANONYMOUS_ACCESS_ERRORS
                    ):
                        pass  # expected: real requests bind as the login user
                    elif settings.config("BASE_DN", default=None):
                        message = (
                            "The configured base entry does not exist or "
                            "cannot be read. Check the BASE_DN setting."
                        )
                        diagnostics.append(
                            Diagnostic(severity="error", message=message)
                        )
                    else:
                        message = (
                            "The auto-detected base entry could not be read. "
                            "Provide the BASE_DN setting."
                        )
                        diagnostics.append(
                            Diagnostic(severity="error", message=message)
                        )

            # Schema readable? A missing/unreadable schema breaks /schema for
            # every user.
            if not settings.SCHEMA_DN:
                if settings.BIND_AS_USER:
                    diagnostics.append(
                        Diagnostic(
                            severity="warning",
                            message="BIND_AS_USER mode: the directory schema "
                            "could not be detected. The schema entry is "
                            "resolved from the SCHEMA_DN setting; consider "
                            "setting it explicitly.",
                        )
                    )
                else:
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
                except (HTTPException, LDAPException) as exc:
                    if settings.BIND_AS_USER and isinstance(
                        exc, ANONYMOUS_ACCESS_ERRORS
                    ):
                        pass  # expected: real requests bind as the login user
                    elif settings.config("SCHEMA_DN", default=None):
                        message = (
                            "The configured schema could not be read. "
                            "Check the SCHEMA_DN setting."
                        )
                        diagnostics.append(
                            Diagnostic(severity="error", message=message)
                        )
                    else:
                        message = (
                            "The auto-detected schema could not be read. "
                            "Provide the SCHEMA_DN setting."
                        )
                        diagnostics.append(
                            Diagnostic(severity="error", message=message)
                        )
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
        elif settings.BIND_AS_USER and not settings.BASE_DN:
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    message="BIND_AS_USER mode: the base entry could not be "
                    "detected because anonymous access is denied. Searches "
                    "resolve it from the BASE_DN setting; consider setting it "
                    "explicitly.",
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
        elif settings.BIND_AS_USER and not settings.SCHEMA_DN:
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    message="BIND_AS_USER mode: the directory schema could "
                    "not be detected because anonymous access is denied. The "
                    "schema entry is resolved from the SCHEMA_DN setting; "
                    "consider setting it explicitly.",
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
