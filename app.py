from collections import OrderedDict
from flask import Flask, jsonify, request, session
from ldap.schema.models import (Entry,
    AttributeType, ObjectClass,
    DITContentRule, DITStructureRule,
    MatchingRule, MatchingRuleUse,
    NameForm)

import ldap, sys


app = Flask( __name__)
app.config.from_object( 'settings')


def _search( expr=app.config['FILTER_ALL'], base=app.config['BASE_DN'], scope=ldap.SCOPE_SUBTREE, attrs=('*','+')):
    con = ldap.initialize( app.config['LDAP_URL'])
    return con.search_s(
        base,
        scope,
        expr,
        attrs)

    
def get_schema() -> None:
    # See: https://hub.packtpub.com/python-ldap-applications-part-4-ldap-schema/
    res = _search( base=app.config['SCHEMA_DN'], scope=ldap.SCOPE_BASE)

    # See: https://www.python-ldap.org/en/latest/reference/ldap-schema.html
    dn, subschema_entry = res[0]
    app.schema = ldap.schema.SubSchema( subschema_entry, check_uniqueness=2)

get_schema()


@app.route( '/')
def index( filename='index.html'): # FIXME Dev mode only, serve statically
    return static_file( 'index.html')


@app.route( '/<filename>')
def static_file( filename): # FIXME Dev mode only, serve statically
    return app.send_static_file( filename)


@app.route( '/api/whoami')
def whoami():
    if request.authorization: 
        res = _search( app.config['FILTER_UID'] % request.authorization['username'])
        if res:
            dn, attrs = res[0]
            return jsonify( dn)
    return jsonify( None)


def dn_sort( dn: str) -> tuple:
    'Re-order DN parts for sorting'
    return tuple( reversed( dn.lower().split( ',')))


def _decode( attrs, filters=None, excludes=None):
    if type( attrs) is dict:
        return { k: _decode( values, filters, excludes) for k, values in attrs.items()
            if (filters is None or k in filters) and (excludes is None or k not in excludes)}
    if attrs == b'TRUE':  return True
    if attrs == b'FALSE': return False
    if type( attrs) is list: return [ _decode( a, filters, excludes) for a in attrs ]
    if type( attrs) is bytes: return str( attrs, app.config['ENCODING'])
    return attrs


@app.route( '/api/tree')
def tree():
    'Dump directory entries as JSON'
    res = dict( _search())
    data, stack = [], []
    for dn in sorted( res.keys(), key=dn_sort):
        attrs = _decode( res[dn], app.config['TREE_ATTRS'])
        attrs['dn'] = dn
        attrs['level'] = len( stack)
        
        # Flatten single-valued lists
        for key in app.config['TREE_ATTRS']: attrs[key] = attrs[key][0]
        
        if not stack:
            stack.append( (dn, attrs))
            dnpart = dn
            attrs['parent'] = None
            
        else:
            rootdn, rootattrs = stack[-1]
            while not dn.endswith( rootdn):
                stack.pop()
                attrs['level'] = len( stack)
                rootdn, rootattrs = stack[-1]
                
            attrs['parent'] = rootdn
            crop = len( rootdn) + 1
            dnpart = dn[:-crop]

            if attrs['hasSubordinates']:
                stack.append( (dn, attrs))
                
        attrs['name'] = dnpart
        data.append( attrs)
        
    return jsonify( data)


@app.route( '/api/entry/<dn>', methods=('GET', 'POST'))
def entry( dn: str):
    'Edit directory entries'
    
    if request.method == 'GET':
        res = _search( base=dn, scope=ldap.SCOPE_BASE)
        if res:
            dn, attrs = res[0]
            ocs = set( _decode( attrs['objectClass']))
            soc = _decode( attrs['structuralObjectClass'][0])
            must_attrs, may_attrs = app.schema.attribute_types( ocs)
            aux = set( app.schema.get_obj( ObjectClass, a).names[0]
                for a in app.schema.get_applicable_aux_classes( soc))
            
            return jsonify( {
                'attrs':  _decode( attrs, excludes=app.config['HIDDEN_ATTRS']
                            | app.config['INTERNAL_ATTRS']),
                'meta': {
                    'dn': dn,
                    'required': [ app.schema.get_obj( AttributeType, a).names[0] for a in must_attrs],
                    'aux': sorted( aux - ocs),
                }
            })

    elif request.method == 'POST':
        return jsonify( request.form.getlist('objectClass')) # FIXME debug code
        
    return jsonify({})
    

### LDAP Schema ###
def _schema( schema_class):
    'Get all objects from the schema for type'
    for oid in app.schema.listall( schema_class):
        obj = app.schema.get_obj( schema_class, oid)
        if not obj.obsolete: yield obj

def _el( obj) -> dict:
    'Basic information about an schema element'
    name = obj.names[0]
    return {
        'oid'      : obj.oid,
        'name'     : name[:1].lower() + name[1:],
        'names'    : obj.names,
        'desc'     : obj.desc,
        'obsolete' : bool( obj.obsolete),
        'sup'      : sorted( obj.sup),
    }

def _kind( i: int) -> str:
    if i==0: return 'structural'
    if i==1: return 'abstract'
    if i==2: return 'auxiliary'
    
def _oc( obj) -> dict:
    'Additional information about an object class'
    r = _el( obj)
    r.update({
        'may'   : sorted( obj.may),
        'must'  : sorted( obj.must),
        'kind'  : _kind( obj.kind)
    })
    return r

def _usage( i: int) -> str:
    'Attribute usage constants'
    if i == 0: return 'userApplications'
    if i == 1: return 'directoryOperation'
    if i == 2: return 'distributedOperation'
    if i == 3: return 'dSAOperation'
    
def _at( obj) -> dict:
    'Additional information about an object class'
    r = _el( obj)
    r.update({
        'single_value' : bool( obj.single_value),
        'no_user_mod'  : bool( obj.no_user_mod),
        'equality'     : obj.equality,
        'syntax'       : obj.syntax,
        'substr'       : obj.substr,
        'ordering'     : obj.ordering,
        'usage'        : _usage( obj.usage),
    })
    return r

def _dict( key: str, items) -> dict:
    'Create an dictionary with a given key'
    return { obj[key].lower() : obj for obj in items }


@app.route( '/api/schema')
def schema():
    return jsonify({
        'attributes'    : _dict( 'name', map( _at, _schema( AttributeType))),
        'objectClasses' : _dict( 'name', map( _oc, _schema( ObjectClass))),
    })
