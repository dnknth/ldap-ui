#!/usr/bin/python

import ldap, sys
from ldap.schema.models import (Entry,
    AttributeType, ObjectClass,
    DITContentRule, DITStructureRule,
    MatchingRule, MatchingRuleUse,
    NameForm)

OC_LIST = ('account', 'person', 'mailboxUser')

con = ldap.initialize( 'ldapi:///', bytes_mode=False)

# See: https://hub.packtpub.com/python-ldap-applications-part-4-ldap-schema/
res = con.search_s('cn=subschema', ldap.SCOPE_BASE, '(objectclass=*)', ['*','+'])

dn, subschema_entry = res[0]

# See: https://www.python-ldap.org/en/latest/reference/ldap-schema.html
schema = ldap.schema.SubSchema( subschema_entry, check_uniqueness=2)

for oid in OC_LIST: # schema.listall( AttributeType):
    print( schema.get_obj( ObjectClass, oid).names)

print( schema.get_obj( ObjectClass, schema.get_structural_oc( OC_LIST)).names)

print( schema.get_obj( AttributeType, 'l').names)
print( schema.get_obj( AttributeType, 'sn').names)
print( schema.get_obj( AttributeType, 'gn').names)
print( schema.get_obj( AttributeType, 'cn').names)

if False:
    must_attrs, may_attrs = schema.attribute_types( OC_LIST)

    for oid, attr_obj in must_attrs.items():
        print( "Must have %s" % attr_obj.names[0], type( attr_obj))

    for oid, attr_obj in may_attrs.items():
        print( "May have %s" % attr_obj.names[0])

