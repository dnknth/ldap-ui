import os
from typing import Optional

from starlette.config import Config

config = Config(".env")

# App settings
DEBUG = config("DEBUG", cast=lambda x: bool(x), default=False)
PREFERRED_URL_SCHEME = "https"
SECRET_KEY = os.urandom(16)

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

USE_TLS = config(
    "USE_TLS",
    cast=lambda x: bool(x),
    default=LDAP_URL.startswith("ldaps://"),
)

# DANGEROUS: Disable TLS host name verification.
INSECURE_TLS = config(
    "INSECURE_TLS",
    cast=lambda x: bool(x),
    default=False,
)

#
# Binding
#


def GET_BIND_DN() -> Optional[str]:
    """
    Try to find a hard-wired DN from in the environment.
    If this is present and GET_BIND_PASSWORD returns something,
    the UI will NOT ask for a login.
    You need to secure it otherwise!
    """
    if config("BIND_DN", default=None):
        return config("BIND_DN")


def GET_BIND_PATTERN(username) -> Optional[str]:
    """
    Apply an optional user DN pattern for authentication
    from the environment,
    e.g. "uid=%s,ou=people,dc=example,dc=com".
    This can be used to authenticate with directories
    that do not allow anonymous users to search.
    """
    if config("BIND_PATTERN", default=None) and username:
        return config("BIND_PATTERN") % username


def GET_BIND_DN_FILTER(username) -> str:
    "Produce a LDAP search filter for the login DN"
    return SEARCH_PATTERNS[0] % username


def GET_BIND_PASSWORD() -> Optional[str]:
    "Try to determine the login password from the environment or request"
    pw = config("BIND_PASSWORD", default=None)
    if pw is not None:
        return pw

    pw_file = config("BIND_PASSWORD_FILE", default=None)
    if pw_file is not None:
        with open(pw_file) as file:
            return file.read().rstrip("\n")


#
# Search
#

# Attribute to search for user names
LOGIN_ATTR = config("LOGIN_ATTR", default="uid")

# Search users by a number of common attributes
SEARCH_PATTERNS = (
    "(%s=%%s)" % LOGIN_ATTR,
    "(cn=%s*)",
    "(gn=%s*)",
    "(sn=%s*)",
)

SEARCH_QUERY_MIN = config(
    "SEARCH_QUERY_MIN",  # Minimum length of query term
    cast=int,
    default=2,
)

SEARCH_MAX = config(
    "SEARCH_MAX",  # Maximum number of results
    cast=int,
    default=50,
)
