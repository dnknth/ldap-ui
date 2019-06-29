from quart import request
from ldap.modlist import addModlist, modifyModlist
import asyncio, base64, quart, functools, io, ldap, ldif, sys, types
from typing import *


app = quart.Quart( __name__)
app.config.from_object( 'settings')

# Constant to add technical attributes in LDAP search results
WITH_OPERATIONAL_ATTRS = ('*','+')

# HTTP 401 headers
UNAUTHORIZED = { 'WWW-Authenticate': 'Basic realm="Login Required"' }

# Special fields
PHOTO = 'jpegPhoto'

# Special syntaxes
OCTET_STRING = '1.3.6.1.4.1.1466.115.121.1.40'


def authenticated( view: Callable):
    ''' Require authentication for a view,
        set up the LDAP connection
        and authenticate against the directory
        with a simple_bind
    '''

    @functools.wraps( view)
    async def wrapped_view( **values):
        if not request.authorization: 
            return quart.Response(
                'Please log in', 401, UNAUTHORIZED)
            
        try:
            # Set up LDAP connection
            request.ldap = ldap.initialize( app.config['LDAP_URL'])

            # Search user in HTTP headers
            res = await result_list( request.ldap.search( 
                app.config['BASE_DN'],
                ldap.SCOPE_SUBTREE,
                '(%s=%s)' % (app.config['LOGIN_ATTR'], request.authorization.username)))
            if len( res) != 1:
                raise ldap.INVALID_CREDENTIALS( {
                    'desc': 'Invalid user',
                    'info': "User '%s' unknown" % request.authorization.username})

            # Found one, try authenticating
            dn, _attrs = res[0]
            await discard( 
                request.ldap.simple_bind( dn, request.authorization.password))

            # On success, call the view function and release connection
            data = await view( **values)
            request.ldap.unbind_s()
            return data

        except ldap.INVALID_CREDENTIALS:
            return quart.Response(
                'Please log in', 401, UNAUTHORIZED)

        except ldap.LDAPError as err:
            args = err.args[0]
            quart.abort( quart.make_response( '%s: %s' % (
                args.get( 'desc', ''),
                args.get( 'info', '')), 500, []))

    return wrapped_view


def api( view: Callable) -> quart.Response:
    ''' View decorator for JSON endpoints.
        Forces authentication.
    '''
    @functools.wraps( view)
    async def wrapped_view( **values) -> quart.Response:
        data = await authenticated( view)( **values)
            
        if type( data) is quart.Response: return data
        elif type( data) is types.GeneratorType:
            return quart.Response( quart.json.dumps( list( data)),
                content_type='application/json')
        return quart.jsonify( data)
    return wrapped_view


def no_cache( view: types.FunctionType) -> quart.Response:
    'View decorator to prevent browser caching. Must precede @api.'
    
    @functools.wraps( view)
    async def wrapped_view( **values) -> quart.Response:
        resp = await view( **values)
        resp.headers[ 'Cache-Control'] = 'no-cache, no-store, must-revalidate'
        resp.headers[ 'Pragma'] = 'no-cache'
        resp.headers[ 'Expires'] = '0'
        return resp
    return wrapped_view


async def result( msgid: int) -> AsyncGenerator[dict, None]:
    'Concurrently gather results'
    while True:
        r_type, r_data = request.ldap.result( msgid=msgid, all=0, timeout=0)
        if r_type is None: await asyncio.sleep( 0.01)
        elif r_data == []: break
        else: yield r_data[0]


async def result_list( msgid: int) -> List[dict]:
    'Concurrently collect a result list'
    return [ r async for r in result( msgid)]


async def discard( msgid: int) -> None:
    'Concurrently discard results'
    async for _r in result( msgid): pass


@app.route( '/')
async def index() -> quart.Response:
    'Serve the main page'
    return await static_file( 'index.html')


@app.route( '/<path:filename>')
async def static_file( filename: str) -> quart.Response:
    'Serve static assets'
    return await app.send_static_file( filename)


@app.route( '/api/whoami')
@no_cache
@api
async def whoami() -> str:
    'DN of the current user'
    return request.ldap.whoami_s().replace( 'dn:', '')


def dn_sort( dn: str) -> tuple:
    'Re-order DN parts for sorting'
    return tuple( reversed( dn.lower().split( ',')))


@app.route( '/api/tree/<basedn>')
@no_cache
@api
async def tree( basedn: str) -> Generator[dict, None, None]:
    'List directory entries'
    
    scope = ldap.SCOPE_ONELEVEL
    if basedn == 'base':
        scope = ldap.SCOPE_BASE
        basedn = app.config['BASE_DN']
            
    res = { k: v async for k, v in result( request.ldap.search(
        basedn, scope, attrlist=WITH_OPERATIONAL_ATTRS))}

    # Return result generator
    # Cannot simply yield in the main tree view
    # because the Ldap bind must run in the request context
    return ( { 'dn': dn,
               'structuralObjectClass' : res[dn]['structuralObjectClass'][0].decode(),
               'hasSubordinates': b'TRUE' == res[dn]['hasSubordinates'][0] }
        for dn in sorted( res.keys(), key=dn_sort))
        

def _entry( res: Tuple[ str, Any]) -> Dict[ str, Any]:
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
async def entry( dn: str) -> Optional[dict]:
    'Edit directory entries'
    
    if request.is_json:
        json = await request.get_json()
        # Copy JSON payload into a dictionary of non-empty byte strings
        req  = { k: [ s.encode() for s in filter( None, v) ]
                    for k,v in json.items()
                    if k != PHOTO}
        
    if request.method == 'GET':
        res = await result_list( request.ldap.search( dn, ldap.SCOPE_BASE))
        return _entry( res[0]) if res else None

    elif request.method == 'POST':
        # Get previous values from directory
        res = await result_list( request.ldap.search( dn, ldap.SCOPE_BASE))
        
        mods = { k: v for k, v in res[0][1].items() if k in req }
        modlist = modifyModlist( mods, req)
        
        if modlist: # Apply changes and send changed keys back
            await discard( request.ldap.modify( dn, modlist))
        return { 'changed' : sorted( set( m[1] for m in modlist)) }
    
    elif request.method == 'PUT':
        # Create new object
        modlist = addModlist( req)
        if modlist:
            await discard( request.ldap.add( dn, modlist))
        return { 'changed' : ['dn'] } # Dummy
        
    elif request.method == 'DELETE':
        await discard( request.ldap.delete( dn))
    
    return None # for mypy


@app.route( '/api/blob/<attr>/<int:index>/<path:dn>', methods=( 'GET', 'DELETE', 'PUT'))
@no_cache
@api
async def blob( attr: str, index: int, dn: str):
    res = await result_list( request.ldap.search( dn, ldap.SCOPE_BASE))
    if not res: quart.abort( 404)
    _dn, attrs = res[0]

    if request.method == 'GET':
        if attr not in attrs or len( attrs[attr]) <= index:
            quart.abort( 404)
        resp = quart.Response( attrs[attr][index],
            content_type='application/octet-stream')
        resp.headers['Content-Disposition'] = \
            'attachment; filename="%s-%d.bin"' % (attr, index)
        return resp

    elif request.method == 'PUT':
        data = [(await request.files)['blob'].read()]
        if attr in attrs:
            await discard(
                request.ldap.modify( dn, [(1, attr, None), (0, attr, data + attrs[attr])]))
        else: await discard( request.ldap.modify( dn, [(0, attr, data)]))

    elif request.method == 'DELETE':
        if attr not in attrs or len( attrs[attr]) <= index:
            quart.abort( 404)
        await discard( request.ldap.modify( dn, [(1, attr, None)]))
        data = attrs[attr][:index] + attrs[attr][index + 1:]
        if data: await discard( request.ldap.modify( dn, [(0, attr, data)]))

    return { 'changed' : [attr] } # dummy
    

@app.route( '/api/ldif/<path:dn>')
@no_cache
@authenticated
async def ldifDump( dn: str) -> quart.Response:
    'Dump an entry as LDIF'
    
    res = await result_list( request.ldap.search( dn, ldap.SCOPE_SUBTREE))
    def to_ldif():
        for dn, attrs in res:
            out = io.StringIO()
            ldif.LDIFWriter( out).unparse( dn, attrs)
            yield out.getvalue()
            
    resp = quart.Response( "".join( to_ldif()),
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
async def ldifUpload() -> quart.Response:
    'Import LDIF'
    
    reader = LDIFReader( await request.data, request.ldap)
    reader.parse()
    return reader.count


@app.route( '/api/rename/<newrdn>/<path:dn>')
@no_cache
@api
async def rename( dn: str, newrdn: str) -> None:
    'Rename an entry'

    await discard( request.ldap.rename( dn, newrdn, delold=0))


def _ename( entry: dict) -> Optional[str]:
    'Try to extract a CN'
    return entry['cn'][0].decode() if entry['cn'] else None


@app.route( '/api/entry/password/<path:dn>', methods=('POST',))
@no_cache
@api
async def passwd( dn: str) -> Optional[bool]:
    'Edit directory entries'
    
    if request.is_json:
        args = await request.get_json()
        if 'check' in args:
            try:
                con = ldap.initialize( app.config['LDAP_URL'])
                con.simple_bind_s( dn, args['check'])
                con.unbind_s()
                return True
            except ldap.INVALID_CREDENTIALS:
                return False
        elif 'new1' in args:
            await discard( request.ldap.passwd( dn, args['old'], args['new1']))

    return None # mypy


@app.route( '/api/search/<path:query>')
@no_cache
@api
async def search( query: str) -> Iterable[ dict]:
    'Search the directory'

    q = query
    patterns = app.config['SEARCH_PATTERNS']

    # Search for an attribute prefix
    if '=' in query:
        attr, q = query.split( '=', 1)
        patterns = ['(%s=%%s*)' % attr]

    # Build query
    if len(q) < app.config['SEARCH_QUERY_MIN']: return []
    query = '(|%s)' % ''.join( pattern % q for pattern in patterns)
    
    res = await result_list( request.ldap.search(
        app.config['BASE_DN'], ldap.SCOPE_SUBTREE, query))
    
    return ( { 'dn': dn, 'name': _ename( attrs) or dn }
        for dn, attrs in res[:app.config['SEARCH_MAX']])


### LDAP Schema ###
app.schema = None


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
async def schema() -> dict:
    'Dump the schema'

    # Load schema into the app
    if app.schema is None:
        # See: https://hub.packtpub.com/python-ldap-applications-part-4-ldap-schema/
        res = await result_list( request.ldap.search( app.config['SCHEMA_DN'],
            ldap.SCOPE_BASE, attrlist=WITH_OPERATIONAL_ATTRS))

        # See: https://www.python-ldap.org/en/latest/reference/ldap-schema.html
        _dn, subschema_entry = res[0]
        app.schema = ldap.schema.SubSchema( subschema_entry, check_uniqueness=2)


    return dict( attributes = _dict( 'name', map( _at, 
                            _schema( ldap.schema.models.AttributeType))),
              objectClasses = _dict( 'name', map( _oc,
                            _schema( ldap.schema.models.ObjectClass))),
                   syntaxes = _dict( 'oid', map( _syntax,
                            _schema( ldap.schema.models.LDAPSyntax))))
