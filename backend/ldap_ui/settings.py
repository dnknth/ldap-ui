import logging
from pathlib import Path

from ldap3.utils.conv import escape_filter_chars
from ldap3.utils.dn import escape_rdn
from starlette.config import Config

#
# App settings
#

# Only load a .env file if one is present, so we avoid starlette's
# "Config file '.env' not found" warning in clean checkouts.
_env = Path(".env")
config = Config(_env) if _env.is_file() else Config()
del _env


def _boolean(b) -> bool:
    return b if isinstance(b, bool) else str(b).lower() in ("true", "yes", "1")


DEBUG = config("DEBUG", cast=lambda x: bool(x), default=False)
MAX_LDIF_SIZE = config(
    "MAX_LDIF_SIZE",
    cast=int,
    default=10 * 1024 * 1024,
)
MAX_BLOB_SIZE = config(
    "MAX_BLOB_SIZE",
    cast=int,
    default=1024 * 1024,
)


#
# LDAP settings
#


LDAP_URL = config("LDAP_URL", default="ldap:///")

# Directory base DN.
# If unset, auto-detection from the root DSE is attempted.
# This works under the following conditions:
# - The root DSE is readable with anonymous binding
# - `namingContexts` contains exactly one entry
# Otherwise, manual configuration is required.
BASE_DN = config("BASE_DN", default=None)

# DN to obtain the directory schema.
# If unset, auto-detection from the root DSE is attempted.
# This works if root DSE is readable with anonymous binding.
# Otherwise, manual configuration is required.
SCHEMA_DN = config("SCHEMA_DN", default=None)

USE_TLS = config("USE_TLS", cast=_boolean, default=LDAP_URL.startswith("ldaps://"))

# DANGEROUS: Disable TLS host name verification.
INSECURE_TLS = config("INSECURE_TLS", cast=_boolean, default=False)

#
# Binding
#


def GET_BIND_PATTERN(username: str | None) -> str | None:
    """
    Apply an optional user DN pattern for authentication
    from the environment,
    e.g. "uid=%s,ou=people,dc=example,dc=com".
    This can be used to authenticate with directories
    that do not allow anonymous users to search.
    User supplied values are escaped according to RFC4514 because
    the resulting string is a Distinguished Name.
    """
    pattern = config("BIND_PATTERN", default=None)

    if pattern is None or username is None:
        return

    if pattern.count("%s") != 1:
        raise ValueError("BIND_PATTERN must contain exactly one '%s' placeholder.")

    return pattern % escape_rdn(username)


def GET_BIND_DN_FILTER(username: str) -> str:
    "Produce a LDAP search filter for the login DN"
    return SEARCH_PATTERNS[0] % escape_filter_chars(username)


#
# Search
#


# Attribute to search for user names
LOGIN_ATTR = config("LOGIN_ATTR", default="uid")

# Search users by a number of common attributes
SEARCH_PATTERNS = (
    f"({LOGIN_ATTR}=%s)",
    "(cn=%s*)",
    "(gn=%s*)",
    "(sn=%s*)",
)

SEARCH_QUERY_MIN = config(
    "SEARCH_QUERY_MIN",  # Minimum length of query term
    cast=int,
    default=2,
)

SEARCH_MAX = min(
    config(
        "SEARCH_MAX",  # Maximum number of results
        cast=int,
        default=50,
    ),
    1000,
)

#
# Security
#


def log_warnings():
    if INSECURE_TLS or not USE_TLS:
        logging.getLogger(__name__).warning(
            "Insecure LDAP connection, check TLS settings"
        )
