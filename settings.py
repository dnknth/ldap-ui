ENV = 'development'
PREFERRED_URL_SCHEME = 'https'
SECRET_KEY = b'\x95\xf9(\xc6\xcb\x05\x1b\xea\x10\xc5\xe8\x97\xcfa\x98\xa2' # obtained via os.urandom(16)

LDAP_URL = 'ldapi:///'
BASE_DN = 'dc=krachbumm,dc=de'
SCHEMA_DN = 'cn=subschema'
ENCODING = 'UTF8'

INTERNAL_ATTRS = set( ('createTimestamp', 'creatorsName', 'modifiersName', 'modifyTimestamp'))
HIDDEN_ATTRS = set( ('entryCSN', 'entryDN', 'entryUUID', 'subschemaSubentry', 'hasSubordinates', 'memberOf'))
TREE_ATTRS = set( ('structuralObjectClass', 'hasSubordinates'))

FILTER_ALL = '(objectclass=*)'
FILTER_UID = '(uid=%s)'