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
BASE_DN = config("BASE_DN", default=None)

USE_TLS = config(
    "USE_TLS",
    cast=lambda x: bool(x),
    default=LDAP_URL.startswith("ldaps://"),
)
INSECURE_TLS = config("INSECURE_TLS", cast=lambda x: bool(x), default=False)

SCHEMA_DN = config("SCHEMA_DN", default="cn=subschema")


#
# Binding
#
def GET_BIND_DN(username) -> Optional[str]:
    "Try to determine the login DN from the environment and request"

    # Use a hard-wired DN from the environment.
    # If this is set and a GET_BIND_PASSWORD returns something,
    # the UI will NOT ask for a login.
    # You need to secure it otherwise!
    if config("BIND_DN", default=None):
        return config("BIND_DN")

    # Optional user DN pattern string for authentication,
    # e.g. "uid=%s,ou=people,dc=example,dc=com".
    # This can be used to authenticate with directories
    # that do not allow anonymous users to search.
    elif config("BIND_PATTERN", default=None) and username:
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
    "SEARCH_QUERY_MIN", cast=int, default=2
)  # Minimum length of query term
SEARCH_MAX = config("SEARCH_MAX", cast=int, default=50)  # Maximum number of results
