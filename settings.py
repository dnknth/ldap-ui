import os

# App settings
PREFERRED_URL_SCHEME = 'https'
SECRET_KEY = os.urandom( 16)

# LDAP settings
LDAP_URL = os.environ.get( 'LDAP_URL', 'ldap:///')
BASE_DN = os.environ.get( 'BASE_DN') # Always required
assert BASE_DN, "BASE_DN environment variable must be set"

SCHEMA_DN = 'cn=subschema'

# Attribute to check for user login
LOGIN_ATTR = os.environ.get( 'LOGIN_ATTR', 'uid')

# Binding
# If the two following attributes are set in the environment,
# the UI will NOT ask for a login.
# You need to secure it otherwise!
BIND_DN = os.environ.get( 'BIND_DN')
BIND_PASSWORD = os.environ.get( 'BIND_PASSWORD')
BIND_PATTERN = os.environ.get('BIND_PATTERN')

# Searches
SEARCH_PATTERNS = ( # for search field
    '(%s=%%s)' % LOGIN_ATTR,
    '(cn=%s)',
    '(gn=%s)',
    '(sn=%s)',
)
SEARCH_QUERY_MIN = 2 # Minimm length of query term
SEARCH_MAX = 50 # Maximum number of results
