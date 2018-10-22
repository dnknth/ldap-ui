import os

# App settings
PREFERRED_URL_SCHEME = 'https'
SECRET_KEY = os.urandom( 16)

# LDAP settings
LDAP_URL = os.environ.get( 'LDAP_URL', 'ldap:///')
BASE_DN = os.environ.get( 'BASE_DN')
SCHEMA_DN = 'cn=subschema'

# Attribute to check for user login
LOGIN_ATTR = os.environ.get( 'LOGIN_ATTR', 'uid')

# Searches
SEARCH_PATTERNS = ( # for search field
    '(%s=%%s)' % LOGIN_ATTR, 
    '(cn=%s)',
    '(gn=%s)',
    '(sn=%s)',
)
SEARCH_QUERY_MIN = 2 # Minimm length of query term
SEARCH_MAX = 50 # Maximum number of results
