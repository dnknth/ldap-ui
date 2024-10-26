# Fast and versatile LDAP editor

This is a *minimal* web interface for LDAP directories. Docker images for `linux/amd64` and `linux/arm64/v8` are [available](https://hub.docker.com/r/dnknth/ldap-ui).

![Screenshot](https://github.com/dnknth/ldap-ui/blob/main/screenshot.png?raw=true)

Features:

* Directory tree view
* Entry creation / modification / deletion
* LDIF import / export
* Image support for the `jpegPhoto` and `thumbnailPhoto` attributes
* Schema aware
* Simple search (configurable)
* Asynchronous LDAP backend with decent scalability
* Available as [Docker image](https://hub.docker.com/r/dnknth/ldap-ui/)

The app always requires authentication, even if the directory permits anonymous access. User credentials are validated through a simple `bind` on the directory (SASL is not supported). What a particular user can see (and edit) is governed entirely by directory access rules. The app shows the directory contents, nothing less and nothing more.

## Usage

### Environment variables

LDAP access is controlled by these environment variables, possibly from a `.env` file:

* `LDAP_URL` (optional): Connection URL, defaults to `ldap:///`.
* `BASE_DN` (required): Search base, e.g. `dc=example,dc=org`.
* `LOGIN_ATTR` (optional): User name attribute, defaults to `uid`.

* `USE_TLS` (optional): Enable TLS, defaults to true for `ldaps` connections. Set it to a non-empty string to force `STARTTLS` on `ldap` connections.
* `INSECURE_TLS` (optional): Do not require a valid server TLS certificate, defaults to false, implies `USE_TLS`.

For finer-grained control, see [settings.py](settings.py).

### Docker

For the impatient: Run it with

```shell
docker run -p 127.0.0.1:5000:5000 \
    -e LDAP_URL=ldap://your.ldap.server/ \
    -e BASE_DN=dc=example,dc=org dnknth/ldap-ui
```

For the even more impatient: Start a demo with

```shell
docker compose up -d
```

and go to <http://localhost:5000/>. You are automatically logged in as `Fred Flintstone`.

### Pip

Install the `python-ldap` dependency with your system's package manager.
Otherwise, Pip will try to compile it from source and this will likely fail because it lacks a development environment.

Then install `ldap-ui` in a virtual environment:

```shell
python3 -m venv --system-site-packages venv
. venv/bin/activate
pip3 install ldap-ui
```

Possibly after a shell `rehash`, it is available as `ldap-ui`:

```text
Usage: ldap-ui [OPTIONS]

Options:
  -b, --base-dn TEXT              LDAP base DN. Required unless the BASE_DN
                                  environment variable is set.
  -h, --host TEXT                 Bind socket to this host.  [default:
                                  127.0.0.1]
  -p, --port INTEGER              Bind socket to this port. If 0, an available
                                  port will be picked.  [default: 5000]
  -l, --log-level [critical|error|warning|info|debug|trace]
                                  Log level. [default: info]
  --version                       Display the current version and exit.
  --help                          Show this message and exit.
```

## Development

Prerequisites:

* [GNU make](https://www.gnu.org/software/make/)
* [node.js](https://nodejs.dev) LTS version with NPM
* [Python3](https://www.python.org) ≥ 3.7
* [pip3](https://packaging.python.org/tutorials/installing-packages/)
* [python-ldap](https://pypi.org/project/python-ldap/); To compile the Python module:
  * Debian / Ubuntu: `apt-get install libsasl2-dev python-dev libldap2-dev libssl-dev`
  * RedHat / CentOS: `yum install python-devel openldap-devel`

`ldap-ui` consists of a Vue frontend and a Python backend that roughly translates a subset of the LDAP protocol to a stateless ReST API.

For the frontend, `npm run build` assembles everything in `backend/ldap_ui/statics`.

Review the configuration in [settings.py](settings.py). It is short and mostly self-explaining.
Most settings can (and should) be overridden by environment variables or settings in a `.env` file; see [env.demo](env.demo) or [env.example](env.example).

The backend can be run locally with `make`, which will also install dependencies and build the frontend if needed.

## Notes

### Authentication methods

The UI always uses a simple `bind` operation to authenticate with the LDAP directory. How the `bind` DN is obtained from a given user name depends on a combination of OS environment variables, possibly from a `.env` file:

1. Search by some attribute. By default, this is the `uid`, which can be overridden by the environment variable `LOGIN_ATTR`, e.g. `LOGIN_ATTR=cn`.
2. If the environment variable `BIND_PATTERN` is set, then no search is performed. Login with a full DN can be configured with `BIND_PATTERN=%s`, which for example allows to login as user `cn=admin,dc=example,dc=org`. If a partial DN like `BIND_PATTERN=%s,dc=example,dc=org` is configured, the corresponding login would be `cn=admin`. If a specific pattern like `BIND_PATTERN=cn=%s,dc=example,dc=org` is configured, the login name is just `admin`.
3. If security is no concern, then a fixed `BIND_DN` and `BIND_PASSWORD` can be set in the environment. This is for demo purposes only, and probably a very bad idea if access to the UI is not restricted by any other means.

### Searching

Search uses a (configurable) set of criteria (`cn`, `gn`, `sn`, and `uid`) if the query does not contain `=`.
Wildcards are supported, e.g. `f*` will match all `cn`, `gn`, `sn`, and `uid` starting with `f`.
Additionally, arbitrary attributes can be searched with an LDAP filter specification, for example `sn=F*`.

### Caveats

* The software works with [OpenLdap](http://www.openldap.org) using simple bind. Other directories have not been tested, and SASL authentication schemes are presently not supported.
* Passwords are transmitted as plain text. The LDAP server is expected to hash them (OpenLdap 2.4 does). I strongly recommend to expose the app through a TLS-enabled web server.
* HTTP *Basic Authentication* is triggered unless the `AUTHORIZATION` request variable is already set by some upstream HTTP server.

## Q&A

* Q: Why are some fields not editable?
  * A: The RDN of an entry is read-only. To change it, rename the entry with a different RDN, then change the old RDN and rename back. To change passwords, click on the question mark icon on the right side. Binary fields (as per schema) are read-only. You do not want to modify them accidentally.
* Q: Why did you write this?
  * A: [PHPLdapAdmin](http://phpldapadmin.sf.net/) has not seen updates for ages. I needed a replacement, and wanted to try Vue.

## Acknowledgements

The Python backend uses [Starlette](https://starlette.io). The UI is built with [Vue.js](https://vuejs.org) and [Tailwind CSS](https://tailwindcss.com/). Kudos to the authors of these elegant frameworks!
