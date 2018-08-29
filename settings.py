import os

# App settings
PREFERRED_URL_SCHEME = 'https'
SECRET_KEY = os.urandom( 16)

# LDAP settings
LDAP_URL = os.environ.get( 'LDAP_URL', 'ldapi:///')
BASE_DN = os.environ.get( 'BASE_DN', 'dc=krachbumm,dc=de')
SCHEMA_DN = 'cn=subschema'
ENCODING = 'UTF8'

# UI settings
TREE_LEVEL = 1 # tree depth shown on page load
HIDDEN_ATTRS = set( ( # Do not change
    'createTimestamp', 'creatorsName',
    'modifiersName', 'modifyTimestamp',
    'entryCSN', 'entryDN', 'entryUUID',
    'subschemaSubentry', 'hasSubordinates',
    'memberOf'))
TREE_ATTRS = set( ( # Do not change
    'structuralObjectClass', 'hasSubordinates'))

# Attribute to check for user login
UID_ATTR = 'uid'

# Searches
SEARCH_PATTERNS = ( # for search field
    '(%s=%%s)' % UID_ATTR, 
    '(cn=%s)',
    '(gn=%s)',
    '(sn=%s)',
)
SEARCH_QUERY_MIN = 2 # Minimm length of query term
SEARCH_MAX = 30 # Maximum number of results
