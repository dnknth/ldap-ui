from quart import request
from ldap.modlist import addModlist, modifyModlist
import asyncio, base64, quart, functools, io, ldap, ldif, sys, types
from typing import *


app = quart.Quart(__name__, static_folder='dist')
if quart.helpers.get_debug_flag():
    from quart_cors import cors
    app = cors(app, allow_origin='*')
app.config.from_object('settings')

# Constant to add technical attributes in LDAP search results
WITH_OPERATIONAL_ATTRS = ('*','+')

# HTTP 401 headers
UNAUTHORIZED = { 'WWW-Authenticate': 'Basic realm="Login Required"' }

# Special fields
PHOTO = 'jpegPhoto'
PASSWORDS = ('userPassword',)

# Special syntaxes
OCTET_STRING = '1.3.6.1.4.1.1466.115.121.1.40'


def authenticated(view: Callable):
    ''' Require authentication for a view,
        set up the LDAP connection
        and authenticate against the directory
        with a simple_bind
    '''

    @functools.wraps(view)
    async def wrapped_view(**values):
        if not request.authorization and not app.config['BIND_DN']:
            return quart.Response(
                'Please log in', 401, UNAUTHORIZED)

        try:
            # Set up LDAP connection
            request.ldap = ldap.initialize(app.config['LDAP_URL'])

            if app.config['BIND_DN'] and app.config['BIND_PASSWORD']:
                dn = app.config['BIND_DN']
                pw = app.config['BIND_PASSWORD']

            elif app.config['BIND_PATTERN']:
                dn = app.config['BIND_PATTERN'] % (request.authorization.username)
                pw = request.authorization.password

            else: # Search user in HTTP headers
                pw = request.authorization.password
                try:
                    dn, _attrs = await unique(request.ldap.search(
                        app.config['BASE_DN'],
                        ldap.SCOPE_SUBTREE,
                        '(%s=%s)' % (app.config['LOGIN_ATTR'], request.authorization.username)))
                except ValueError:
                    raise ldap.INVALID_CREDENTIALS({
                        'desc': 'Invalid user',
                        'info': "User '%s' unknown" % request.authorization.username})

            # Try authenticating
            await empty(request.ldap.simple_bind(dn, pw))

            # On success, call the view function and release connection
            data = await view(**values)
            request.ldap.unbind_s()
            return data

        except ldap.INVALID_CREDENTIALS:
            return quart.Response(
                'Please log in', 401, UNAUTHORIZED)

        except ldap.LDAPError as err:
            args = err.args[0]
            quart.abort(500, args.get('info', '')
                + ': ' + args.get('desc', ''))

    return wrapped_view


def api(view: Callable) -> quart.Response:
    ''' View decorator for JSON endpoints.
        Forces authentication.
    '''
    @functools.wraps(view)
    async def wrapped_view(**values) -> quart.Response:
        data = await authenticated(view)(**values)
        if type(data) is not quart.Response:
            data = quart.jsonify(data)
        return data
    return wrapped_view


def no_cache(view: types.FunctionType) -> quart.Response:
    'View decorator to prevent browser caching. Must precede @api.'
    
    @functools.wraps(view)
    async def wrapped_view(**values) -> quart.Response:
        resp = await view(**values)
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
        return resp
    return wrapped_view


async def result(msgid: int,) -> AsyncGenerator[Tuple[str, Dict[str, List[bytes]]], None]:
    'Concurrently gather results'
    while True:
        r_type, r_data = request.ldap.result(msgid=msgid, all=0, timeout=0)
        # Throttle to 100 results / second
        if r_type is None: await asyncio.sleep(0.01)
        elif r_data == []: break
        else: yield r_data[0]


async def unique(msgid: int) -> Tuple[str, Dict[str, List[bytes]]]:
    'Concurrently collect a unique result'
    res = None
    async for r in result(msgid):
        if res is None: res = r
        else:
            request.ldap.abandon(msgid)
            raise ValueError("Expected unique result")
    if res is None: 
        raise ValueError("Expected unique result")
    return res


async def empty(msgid: int) -> None:
    'Concurrently wait for an empty result'
    async for r in result(msgid):
        request.ldap.abandon(msgid)
        raise ValueError("Unexpected result")


@app.route('/')
async def index() -> quart.Response:
    'Serve the main page'
    return await static_file('index.html')


@app.route('/<path:filename>')
async def static_file(filename: str) -> quart.Response:
    'Serve static assets'
    return await app.send_static_file(filename)


@app.route('/api/whoami')
@no_cache
@api
async def whoami() -> str:
    'DN of the current user'
    return request.ldap.whoami_s().replace('dn:', '')


@app.route('/api/tree/<basedn>')
@no_cache
@api
async def tree(basedn: str) -> List[Dict[str, Any]]:
    'List directory entries'
    
    scope = ldap.SCOPE_ONELEVEL
    if basedn == 'base':
        scope = ldap.SCOPE_BASE
        basedn = app.config['BASE_DN']

    return await _tree(basedn, scope)


async def _tree(basedn: str, scope: int) -> List[Dict[str, Any]]:
    'Get all nodes below a DN (including the DN) within the given scope'

    return [ { 'dn': dn,
               'structuralObjectClass' : attrs['structuralObjectClass'][0].decode(),
               'hasSubordinates': b'TRUE' == attrs['hasSubordinates'][0] }
        async for dn, attrs in result(request.ldap.search(
            basedn, scope, attrlist=WITH_OPERATIONAL_ATTRS)) ]
        

def _entry(res: Tuple[str, Any]) -> Dict[str, Any]:
    'Prepare an LDAP entry for transmission'
    
    dn, attrs = res
    ocs = set([oc.decode() for oc in attrs['objectClass']])
    must_attrs, _may_attrs = app.schema.attribute_types(ocs)
    soc = [oc.names[0]
        for oc in map(lambda o: app.schema.get_obj(ldap.schema.models.ObjectClass, o), ocs)
        if oc.kind == 0]
    aux = set(app.schema.get_obj(ldap.schema.models.ObjectClass, a).names[0]
        for a in app.schema.get_applicable_aux_classes(soc[0]))

    #23 suppress userPassword
    if 'userPassword' in attrs:
        attrs['userPassword'] = [b'*****']
        
    # Filter out binary attributes
    binary = set()
    for attr in attrs:
        obj = app.schema.get_obj(ldap.schema.models.AttributeType, attr)

        # Octet strings are not used consistently.
        # Try to decode as text and treat as binary on failure
        if not obj.syntax or obj.syntax == OCTET_STRING:
            try:
                for val in attrs[attr]:
                    assert val.decode().isprintable()
            except:
                binary.add(attr)

        else: # Check human-readable flag in schema
            syntax = app.schema.get_obj(ldap.schema.models.LDAPSyntax, obj.syntax)
            if syntax.not_human_readable: binary.add(attr)
    
    return {
        'attrs':  { k: [base64.b64encode(val).decode()
                         if k in binary else val.decode()
                         for val in values]
            for k, values in attrs.items() },
        'meta': {
            'dn': dn,
            'required': [app.schema.get_obj(ldap.schema.models.AttributeType, a).names[0]
                          for a in must_attrs],
            'aux': sorted(aux - ocs),
            'binary': sorted(binary),
            'hints': {},
            'autoFilled': [],
        }
    }


@app.route('/api/entry/<path:dn>', methods=('GET', 'POST', 'DELETE', 'PUT'))
@no_cache
@api
async def entry(dn: str) -> Optional[dict]:
    'Edit directory entries'
    
    if request.is_json:
        json = await request.get_json()
        # Copy JSON payload into a dictionary of non-empty byte strings
        req  = { k: [s.encode() for s in filter(None, v)]
                    for k,v in json.items()
                    if k != PHOTO
                    and (k not in PASSWORDS or request.method == 'PUT') }
        
    if request.method == 'GET':
        try:
            return _entry(await unique(request.ldap.search(dn, ldap.SCOPE_BASE)))
        except ValueError:
            return None

    elif request.method == 'POST':
        # Get previous values from directory
        res = await unique(request.ldap.search(dn, ldap.SCOPE_BASE))
        
        mods = { k: v for k, v in res[1].items() if k in req }
        modlist = modifyModlist(mods, req)
        
        if modlist: # Apply changes and send changed keys back
            await empty(request.ldap.modify(dn, modlist))
        return { 'changed' : sorted(set(m[1] for m in modlist)) }
    
    elif request.method == 'PUT':
        # Create new object
        modlist = addModlist(req)
        if modlist: await empty(request.ldap.add(dn, modlist))
        return { 'changed' : ['dn'] } # Dummy
        
    elif request.method == 'DELETE':
        for entry in reversed(sorted(await _tree(dn, ldap.SCOPE_SUBTREE), key=_dn_order)):
            await empty(request.ldap.delete(entry['dn']))
    
    return None # for mypy


@app.route('/api/blob/<attr>/<int:index>/<path:dn>', methods=('GET', 'DELETE', 'PUT'))
@no_cache
@api
async def blob(attr: str, index: int, dn: str):
    try:
        _dn, attrs = await unique(request.ldap.search(dn, ldap.SCOPE_BASE))
    except ValueError:
        quart.abort(404)

    if request.method == 'GET':
        if attr not in attrs or len(attrs[attr]) <= index:
            quart.abort(404)
        resp = quart.Response(attrs[attr][index],
            content_type='application/octet-stream')
        resp.headers['Content-Disposition'] = \
            'attachment; filename="%s-%d.bin"' % (attr, index)
        return resp

    elif request.method == 'PUT':
        data = [(await request.files)['blob'].read()]
        if attr in attrs:
            await empty(
                request.ldap.modify(dn, [(1, attr, None), (0, attr, data + attrs[attr])]))
        else: await empty(request.ldap.modify(dn, [(0, attr, data)]))

    elif request.method == 'DELETE':
        if attr not in attrs or len(attrs[attr]) <= index:
            quart.abort(404)
        await empty(request.ldap.modify(dn, [(1, attr, None)]))
        data = attrs[attr][:index] + attrs[attr][index + 1:]
        if data: await empty(request.ldap.modify(dn, [(0, attr, data)]))

    return { 'changed' : [attr] } # dummy
    

@app.route('/api/ldif/<path:dn>')
@no_cache
@authenticated
async def ldifDump(dn: str) -> quart.Response:
    'Dump an entry as LDIF'
    
    out = io.StringIO()
    writer = ldif.LDIFWriter(out)
    async for dn, attrs in result(request.ldap.search(dn, ldap.SCOPE_SUBTREE)):
        writer.unparse(dn, attrs)
            
    resp = quart.Response(out.getvalue(), content_type='text/plain')
    resp.headers['Content-Disposition'] = \
        'attachment; filename="%s.ldif"' % dn.split(',')[0].split('=')[1]
    return resp


class LDIFReader(ldif.LDIFParser):
    def __init__(self, input, con):
        ldif.LDIFParser.__init__(self, io.BytesIO(input))
        self.count = 0
        self.con = con

    def handle(self, dn, entry):
        self.con.add_s(dn, addModlist(entry))
        self.count += 1


@app.route('/api/ldif', methods=('POST',))
@no_cache
@api
async def ldifUpload() -> quart.Response:
    'Import LDIF'
    
    reader = LDIFReader(await request.data, request.ldap)
    reader.parse()
    return reader.count


@app.route('/api/rename/<newrdn>/<path:dn>')
@no_cache
@api
async def rename(dn: str, newrdn: str) -> None:
    'Rename an entry'
    await empty(request.ldap.rename(dn, newrdn, delold=0))
    return 'OK'


def _ename(entry: dict) -> Optional[str]:
    'Try to extract a CN'
    return entry['cn'][0].decode() if 'cn' in entry and entry['cn'] else None


@app.route('/api/entry/password/<path:dn>', methods=('POST',))
@no_cache
@api
async def passwd(dn: str) -> Optional[bool]:
    'Edit directory entries'
    
    if request.is_json:
        args = await request.get_json()
        if 'check' in args:
            try:
                con = ldap.initialize(app.config['LDAP_URL'])
                con.simple_bind_s(dn, args['check'])
                con.unbind_s()
                return True
            except ldap.INVALID_CREDENTIALS:
                return False
                
        elif 'new1' in args:
            await empty(request.ldap.passwd(dn, args.get('old') or None, args['new1']))
            _dn, attrs = await unique(
                request.ldap.search(dn, ldap.SCOPE_BASE))
            return attrs['userPassword'][0].decode()

    return None # mypy


@app.route('/api/search/<path:query>')
@no_cache
@api
async def search(query: str) -> List[dict]:
    'Search the directory'

    patterns = app.config['SEARCH_PATTERNS']
    if len(query) < app.config['SEARCH_QUERY_MIN']: return []

    if '=' in query: # Search specific attributes
        if '(' not in query: query = '(%s)' % query
    else: # Build default query
        query = '(|%s)' % ''.join(p % query for p in patterns)
    
    # Collect results
    res : List[dict] = []
    async for dn, attrs in result(request.ldap.search(
        app.config['BASE_DN'], ldap.SCOPE_SUBTREE, query)):
            res.append({ 'dn': dn, 'name': _ename(attrs) or dn })
            if len(res) >= app.config['SEARCH_MAX']: break
    return res


def _dn_order(node):
    'Reverse DN parts for tree ordering'
    return tuple(reversed(node['dn'].lower().split(',')))


@app.route('/api/subtree/<path:dn>')
@no_cache
@api
async def subtree(dn: str) -> List[str]:
    'List the subtree below a dn'

    result, start = [], len(dn.split(','))
    for node in sorted(await _tree(dn, ldap.SCOPE_SUBTREE), key=_dn_order):
        if node['dn'] == dn: continue
        node['level'] = len(node['dn'].split(',')) - start
        result.append(node)
    return result


@app.route('/api/range/<attribute>')
@no_cache
@api
async def attribute_range(attribute: str) -> List[int]:
    'List all values for a numeric attribute of an objectClass like uidNumber or gidNumber'

    res = set()
    async for dn, attrs in result(request.ldap.search(
        app.config['BASE_DN'], ldap.SCOPE_SUBTREE, '(%s=*)' % attribute, attrlist=(attribute,))):
            res.add(int(attrs[attribute][0]))
    if not res: return {}
    
    minimum, maximum = min(res), max(res)
    return { 'min' : minimum, 'max': maximum,
        'next' : min(set(range(minimum, maximum + 2)) - res) }


### LDAP Schema ###
app.schema = None


def _schema(schema_class):
    'Get all objects from the schema for type'
    for oid in app.schema.listall(schema_class):
        obj = app.schema.get_obj(schema_class, oid)
        if schema_class is ldap.schema.models.LDAPSyntax or not obj.obsolete:
            yield obj

def _el(obj) -> dict:
    'Basic information about an schema element'
    name = obj.names[0]
    return {
        'oid'      : obj.oid,
        'name'     : name[:1].lower() + name[1:],
        'names'    : obj.names,
        'desc'     : obj.desc,
        'obsolete' : bool(obj.obsolete),
        'sup'      : sorted(obj.sup),
    }

# Object class constants
SCHEMA_OC_KIND = {
    0: 'structural',
    1: 'abstract',
    2: 'auxiliary',
}
   
def _oc(obj) -> dict:
    'Additional information about an object class'
    r = _el(obj)
    r.update({
        'may'   : sorted(obj.may),
        'must'  : sorted(obj.must),
        'kind'  : SCHEMA_OC_KIND[obj.kind]
    })
    return r

# Attribute usage constants
SCHEMA_ATTR_USAGE = {
    0: 'userApplications',
    1: 'directoryOperation',
    2: 'distributedOperation',
    3: 'dSAOperation',
}
    
def _at(obj) -> dict:
    'Additional information about an object class'
    r = _el(obj)
    r.update({
        'single_value' : bool(obj.single_value),
        'no_user_mod'  : bool(obj.no_user_mod),
        'equality'     : obj.equality,
        'syntax'       : obj.syntax,
        'substr'       : obj.substr,
        'ordering'     : obj.ordering,
        'usage'        : SCHEMA_ATTR_USAGE[obj.usage],
    })
    return r

def _syntax(obj) -> dict:
    'Additional information about an attribute syntax'
    return {
        'oid'      : obj.oid,
        'desc'     : obj.desc,
        'not_human_readable' : bool(obj.not_human_readable), 
    }

def _dict(key: str, items) -> dict:
    'Create an dictionary with a given key'
    return { obj[key].lower() : obj for obj in items }


@app.route('/api/schema')
@no_cache
@api
async def schema() -> dict:
    'Dump the schema'

    # Load schema into the app
    if app.schema is None:
        # See: https://hub.packtpub.com/python-ldap-applications-part-4-ldap-schema/
        _dn, subschema_entry = await unique(
            request.ldap.search(app.config['SCHEMA_DN'],
            ldap.SCOPE_BASE, attrlist=WITH_OPERATIONAL_ATTRS))

        # See: https://www.python-ldap.org/en/latest/reference/ldap-schema.html
        app.schema = ldap.schema.SubSchema(subschema_entry, check_uniqueness=2)
    
    return dict(attributes = _dict('name', map(_at, 
                            _schema(ldap.schema.models.AttributeType))),
              objectClasses = _dict('name', map(_oc,
                            _schema(ldap.schema.models.ObjectClass))),
                   syntaxes = _dict('oid', map(_syntax,
                            _schema(ldap.schema.models.LDAPSyntax))))
