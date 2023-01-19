from dotenv import load_dotenv
import os

load_dotenv()

# App settings
PREFERRED_URL_SCHEME = 'https'
SECRET_KEY = os.urandom(16)

#
# LDAP settings
#
LDAP_URL = os.environ.get('LDAP_URL', 'ldap:///')
BASE_DN = os.environ.get('BASE_DN') # Always required
assert BASE_DN, "BASE_DN environment variable must be set"

SCHEMA_DN = 'cn=subschema'

#
# Binding
#
def GET_BIND_DN(authorization):
    'Try to determine the login DN from the environment and request'

    # Use a hard-wired DN from the environment.
    # If this is set and a GET_BIND_PASSWORD returns something,
    # the UI will NOT ask for a login.
    # You need to secure it otherwise!
    if os.environ.get('BIND_DN'): return os.environ['BIND_DN']

    # Optional user DN pattern string for authentication,
    # e.g. "uid=%s,ou=people,dc=example,dc=com".
    # This can be used to authenticate with directories
    # that do not allow anonymous users to search.
    elif os.environ.get('BIND_PATTERN') and authorization is not None:
        return os.environ['BIND_PATTERN'] % authorization.username


def GET_BIND_DN_FILTER(authorization):
    'Produce a LDAP search filter for the login DN'
    return SEARCH_PATTERNS[0] % authorization.username


def GET_BIND_PASSWORD(authorization):
    'Try to determine the login password from the environment or request'

    pw = os.environ.get('BIND_PASSWORD')
    if pw is not None: return pw

    pw_file = os.environ.get('BIND_PASSWORD_FILE')
    if pw_file is not None:
        with open(pw_file) as file:
            return file.read().rstrip('\n')
            
    if authorization is not None:
        return authorization.password


#
# Search
#

# Attribute to search for user names
LOGIN_ATTR = os.environ.get('LOGIN_ATTR', 'uid')

# Search users by a number of common attributes
SEARCH_PATTERNS = (
    '(%s=%%s)' % LOGIN_ATTR,
    '(cn=%s)',
    '(gn=%s)',
    '(sn=%s)',
)
SEARCH_QUERY_MIN = 2 # Minimm length of query term
SEARCH_MAX = 50 # Maximum number of results
