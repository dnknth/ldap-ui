from contextlib import contextmanager
from flask import request
from ldap.modlist import addModlist, modifyModlist
import base64, flask, functools, io, ldap, ldif, sys, types, typing


app = flask.Flask( __name__)
app.config.from_object( 'settings')

# Constant to add technical attributes in LDAP search results
WITH_OPERATIONAL_ATTRS = ('*','+')

# HTTP 401 headers
UNAUTHORIZED = { 'WWW-Authenticate': 'Basic realm="Login Required"' }

# Special fields
PHOTO = 'jpegPhoto'

# Special syntaxes
OCTET_STRING = '1.3.6.1.4.1.1466.115.121.1.40'

# Generator function that emits a JSON list for an iterable.
# Makes most sense if data is a subgenerator
# See: https://blog.al4.co.nz/2016/01/streaming-json-with-flask/
def stream_list( data) -> typing.Generator:
    yield '['

    chunks = data.__iter__()
    try:
        r = next( chunks)
        yield flask.json.dumps( r)

        # loop over remaining results
        for r in chunks:
            yield ',' + flask.json.dumps( r)

    except StopIteration:
        pass
        
    # close array
    yield ']'


def authenticated( view: typing.Callable):
    'Require authentication for a view'

    @functools.wraps( view)
    def wrapped_view( **values):
        if not request.authorization: 
            return flask.Response(
                'Please log in', 401, UNAUTHORIZED)
            
        try:
            return view( **values)
        except ldap.INVALID_CREDENTIALS:
            return flask.Response(
                'Please log in', 401, UNAUTHORIZED)
        except ldap.LDAPError as err:
            args = err.args[0]
            flask.abort( flask.make_response( '%s: %s' % (
                args.get( 'desc', ''),
                args.get( 'info', '')), 500, []))
    return wrapped_view


def api( view: typing.Callable) -> flask.Response:
    ''' View decorator for JSON endpoints.
        Requires authentication.
    '''
    @functools.wraps( view)
    def wrapped_view( **values) -> flask.Response:
        data = authenticated( view)( **values)
            
        if type( data) is flask.Response: return data
        elif type( data) is types.GeneratorType:
            return flask.Response( stream_list( data),
                content_type='application/json')
        return flask.jsonify( data)
    return wrapped_view


def no_cache( view: types.FunctionType) -> flask.Response:
    'View decorator to prevent browser caching. Must precede @api.'
    
    @functools.wraps( view)
    def wrapped_view( **values) -> flask.Response:
        resp = view( **values)
        resp.headers[ 'Cache-Control'] = 'no-cache, no-store, must-revalidate'
        resp.headers[ 'Pragma'] = 'no-cache'
        resp.headers[ 'Expires'] = '0'
        return resp
    return wrapped_view


@contextmanager
def Ldap( auth:dict=None):
    'Context manager for authenticated LDAP connections'
    
    connection = ldap.initialize( app.config['LDAP_URL'])
    if auth:
        res = connection.search_s( 
            app.config['BASE_DN'],
            ldap.SCOPE_SUBTREE,
            '(%s=%s)' % (app.config['LOGIN_ATTR'], auth['username']))
        if len( res) != 1:
            raise ldap.INVALID_CREDENTIALS( {
                'desc': 'Invalid user',
                'info': "User '%s' unknown" % auth['username']})
        dn, _attrs = res[0]
        connection.simple_bind_s( dn, auth['password'])
    yield connection
    if auth: connection.unbind_s()


@app.route( '/')
def index() -> flask.Response:
    'Serve the main page'
    return static_file( 'index.html')


@app.route( '/<path:filename>')
def static_file( filename: str) -> flask.Response:
    'Serve static assets'
    return app.send_static_file( filename)


@app.route( '/api/whoami')
@no_cache
@api
def whoami() -> str:
    'DN of the current user'
    with Ldap( request.authorization) as con:
        return con.whoami_s().replace( 'dn:', '')


def dn_sort( dn: str) -> tuple:
    'Re-order DN parts for sorting'
    return tuple( reversed( dn.lower().split( ',')))


@app.route( '/api/tree/<basedn>')
@no_cache
@api
def tree( basedn: str) -> typing.Generator[dict, None, None]:
    'List directory entries'
    
    scope = ldap.SCOPE_ONELEVEL
    if basedn == 'base':
        scope = ldap.SCOPE_BASE
        basedn = app.config['BASE_DN']
            
    with Ldap( request.authorization) as con:
        res = dict( con.search_s( basedn, scope,
            attrlist=WITH_OPERATIONAL_ATTRS))

    # Return result generator
    # Cannot simply yield in the main tree view
    # because the Ldap bind must run in the request context
    return ( { 'dn': dn,
               'structuralObjectClass' : res[dn]['structuralObjectClass'][0].decode(),
               'hasSubordinates': b'TRUE' == res[dn]['hasSubordinates'][0] }
        for dn in sorted( res.keys(), key=dn_sort))
        

def _entry( res: tuple) -> dict:
    'Prepare an LDAP entry for transmission'
    
    dn, attrs = res
    ocs = set( [ oc.decode() for oc in attrs['objectClass'] ])
    must_attrs, _may_attrs = app.schema.attribute_types( ocs)
    soc = [ oc.names[0]
        for oc in map( lambda o: app.schema.get_obj( ldap.schema.models.ObjectClass, o), ocs)
        if oc.kind == 0]
    aux = set( app.schema.get_obj( ldap.schema.models.ObjectClass, a).names[0]
        for a in app.schema.get_applicable_aux_classes( soc[0]))
    
    # Filter out binary attributes
    binary = set()
    for attr in attrs.keys():
        obj = app.schema.get_obj( ldap.schema.models.AttributeType, attr)

        # Octet strings are not used consistently.
        # Try to decode as text and treat as binary on failure
        if not obj.syntax or obj.syntax == OCTET_STRING:
            try:
                for val in attrs[attr]: val.decode()
            except UnicodeError:
                binary.add( attr)

        else: # Check human-readable flag in schema
            syntax = app.schema.get_obj( ldap.schema.models.LDAPSyntax, obj.syntax)
            if syntax.not_human_readable: binary.add( attr)
    
    return {
        'attrs':  { k: [ base64.b64encode( val).decode()
                         if k in binary else val.decode()
                         for val in values ]
            for k, values in attrs.items() },
        'meta': {
            'dn': dn,
            'required': [ app.schema.get_obj( ldap.schema.models.AttributeType, a).names[0]
                          for a in must_attrs],
            'aux': sorted( aux - ocs),
            'binary': sorted( binary),
        }
    }


@app.route( '/api/entry/<path:dn>', methods=('GET', 'POST', 'DELETE', 'PUT'))
@no_cache
@api
def entry( dn: str) -> typing.Optional[dict]:
    'Edit directory entries'
    
    if request.is_json:
        json = request.get_json()
        # Copy JSON payload into a dictionary of non-empty byte strings
        req  = { k: [ s.encode() for s in filter( None, v) ]
                    for k,v in json.items()
                    if k != PHOTO}
        
    with Ldap( request.authorization) as con:
        if request.method == 'GET':
            res = con.search_s( dn, ldap.SCOPE_BASE)
            return _entry( res[0]) if res else None
    
        elif request.method == 'POST':
            # Get previous values from directory
            res = con.search_s( dn, ldap.SCOPE_BASE)
            
            mods = { k: v for k, v in res[0][1].items() if k in req }
            modlist = modifyModlist( mods, req)
            
            if modlist: # Apply changes and send changed keys back
                con.modify_s( dn, modlist)
            return { 'changed' : sorted( set( m[1] for m in modlist)) }
        
        elif request.method == 'PUT':
            # Create new object
            modlist = addModlist( req)
            if modlist: con.add_s( dn, modlist)
            return { 'changed' : ['dn'] } # Dummy
            
        elif request.method == 'DELETE':
            con.delete_s( dn)
        
        return None # for mypy


@app.route( '/api/blob/<attr>/<int:index>/<path:dn>', methods=( 'GET', 'DELETE', 'PUT'))
@no_cache
@api
def blob( attr: str, index: int, dn: str):
    with Ldap( request.authorization) as con:

        res = con.search_s( dn, ldap.SCOPE_BASE)
        if not res: flask.abort( 404)
        _dn, attrs = res[0]

        if request.method == 'GET':
            if attr not in attrs or len( attrs[attr]) <= index:
                flask.abort( 404)
            resp = flask.Response( attrs[attr][index],
                content_type='application/octet-stream')
            resp.headers['Content-Disposition'] = \
                'attachment; filename="%s-%d.bin"' % (attr, index)
            return resp
 
        elif request.method == 'PUT':
            data = [request.files['blob'].read()]
            if attr in attrs:
                con.modify_s( dn, [(1, attr, None), (0, attr, data + attrs[attr])])
            else: con.modify_s( dn, [(0, attr, data)])
    
        elif request.method == 'DELETE':
            if attr not in attrs or len( attrs[attr]) <= index:
                flask.abort( 404)
            con.modify_s( dn, [(1, attr, None)])
            data = attrs[attr][:index] + attrs[attr][index + 1:]
            if data: con.modify_s( dn, [(0, attr, data)])

        return { 'changed' : [attr] } # dummy
    

@app.route( '/api/ldif/<path:dn>')
@no_cache
@authenticated
def ldifDump( dn: str) -> flask.Response:
    'Dump an entry as LDIF'
    
    with Ldap( request.authorization) as con:
        res = con.search_s( dn, ldap.SCOPE_SUBTREE)
        def to_ldif():
            for dn, attrs in res:
                out = io.StringIO()
                ldif.LDIFWriter( out).unparse( dn, attrs)
                yield out.getvalue()
                
        resp = flask.Response( to_ldif(),
            content_type='text/plain')
        resp.headers['Content-Disposition'] = \
            'attachment; filename="%s.ldif"' % dn.split(',')[0].split('=')[1]
        return resp


class LDIFReader( ldif.LDIFParser):
    def __init__( self, input, con):
        ldif.LDIFParser.__init__( self, io.BytesIO( input))
        self.count = 0
        self.con = con

    def handle( self, dn, entry):
        self.con.add_s( dn, addModlist( entry))
        self.count += 1


@app.route( '/api/ldif', methods=('POST',))
@no_cache
@api
def ldifUpload() -> flask.Response:
    'Import LDIF'
    
    with Ldap( request.authorization) as con:
        reader = LDIFReader( request.data, con)
        reader.parse()
        return reader.count


@app.route( '/api/rename/<newrdn>/<path:dn>')
@no_cache
@api
def rename( dn: str, newrdn: str) -> None:
    'Rename an entry'

    with Ldap( request.authorization) as con:
        con.rename_s( dn, newrdn, delold=0)


def _ename( entry: dict) -> typing.Optional[str]:
    'Try to extract a CN'
    return entry['cn'][0].decode() if entry['cn'] else None


@app.route( '/api/entry/password/<path:dn>', methods=('POST',))
@no_cache
@api
def passwd( dn: str) -> None:
    'Edit directory entries'
    
    if request.is_json:
        args = request.get_json()
        if 'check' in args:
            with Ldap() as con:
                try:
                    con.simple_bind_s( dn, args['check'])
                    con.unbind_s()
                    return True
                except ldap.INVALID_CREDENTIALS:
                    return False
        elif 'new1' in args:
            with Ldap( request.authorization) as con:
                con.passwd_s( dn, args['old'], args['new1'])


@app.route( '/api/search/<path:q>')
@no_cache
@api
def search( q: str) -> typing.Iterable[ dict]:
    'Search the directory'
    
    # Build query
    if len(q) < app.config['SEARCH_QUERY_MIN']: return []
    query = '(|%s)' % ''.join( pattern % q
            for pattern in app.config['SEARCH_PATTERNS'])
    
    with Ldap( request.authorization) as con:
        res = con.search_s(
            app.config['BASE_DN'], ldap.SCOPE_SUBTREE, query)
    
    return ( { 'dn': dn, 'name': _ename( attrs) or dn }
        for dn, attrs in res[:app.config['SEARCH_MAX']])


### LDAP Schema ###
def get_schema() -> ldap.schema.SubSchema:
    # See: https://hub.packtpub.com/python-ldap-applications-part-4-ldap-schema/
    with Ldap() as con:
        res = con.search_s( app.config['SCHEMA_DN'],
            ldap.SCOPE_BASE, attrlist=WITH_OPERATIONAL_ATTRS)

        # See: https://www.python-ldap.org/en/latest/reference/ldap-schema.html
        _dn, subschema_entry = res[0]
        return ldap.schema.SubSchema( subschema_entry, check_uniqueness=2)


# Load schema into the app
app.schema = get_schema()


def _schema( schema_class):
    'Get all objects from the schema for type'
    for oid in app.schema.listall( schema_class):
        obj = app.schema.get_obj( schema_class, oid)
        if schema_class is ldap.schema.models.LDAPSyntax or not obj.obsolete:
            yield obj

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

# Object class constants
SCHEMA_OC_KIND = {
    0: 'structural',
    1: 'abstract',
    2: 'auxiliary',
}
   
def _oc( obj) -> dict:
    'Additional information about an object class'
    r = _el( obj)
    r.update({
        'may'   : sorted( obj.may),
        'must'  : sorted( obj.must),
        'kind'  : SCHEMA_OC_KIND[ obj.kind]
    })
    return r

# Attribute usage constants
SCHEMA_ATTR_USAGE = {
    0: 'userApplications',
    1: 'directoryOperation',
    2: 'distributedOperation',
    3: 'dSAOperation',
}
    
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
        'usage'        : SCHEMA_ATTR_USAGE[ obj.usage],
    })
    return r

def _syntax( obj) -> dict:
    'Additional information about an attribute syntax'
    return {
        'oid'      : obj.oid,
        'desc'     : obj.desc,
        'not_human_readable' : bool( obj.not_human_readable), 
    }

def _dict( key: str, items) -> dict:
    'Create an dictionary with a given key'
    return { obj[key].lower() : obj for obj in items }


@app.route( '/api/schema')
@no_cache
@api
def schema() -> dict:
    'Dump the schema'
    return dict( attributes = _dict( 'name', map( _at, 
                            _schema( ldap.schema.models.AttributeType))),
              objectClasses = _dict( 'name', map( _oc,
                            _schema( ldap.schema.models.ObjectClass))),
                   syntaxes = _dict( 'oid', map( _syntax,
                            _schema( ldap.schema.models.LDAPSyntax))))
