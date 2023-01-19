# Simple LDAP editor

This is a *minimal* web interface for LDAP directories.

![Screenshot](screenshot.png?raw=true)

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

### Docker

For the impatient: Run it with

    docker run -p 127.0.0.1:5000:5000 \
      -e LDAP_URL=ldap://your.ldap.server/ \
      -e BASE_DN=dc=example,dc=org dnknth/ldap-ui

For the even more impatient: Start a demo with

    docker compose up -d

and go to [http://localhost:5000/](http://localhost:5000/). You are automatically logged in as `Fred Flintstone`.

#### Environment variables

LDAP access is controlled by these environment variables, possibly from a `.env` file:

* `LDAP_URL` (optional): Connection URL, defaults to `ldap:///`).
* `BASE_DN` (required): Search base, e.g. `dc=example,dc=org`.
* `LOGIN_ATTR` (optional): User name attribute, defaults to `uid`.

For finer-grained control, adjust [settings.py](settings.py).

### Standalone

Copy [env.example](env.example) to `.env` and run the app with

    make run

and head over to [http://localhost:5000/](http://localhost:5000/).

## Manual installation and configuration

Prerequisites:

* [GNU make](https://www.gnu.org/software/make/)
* [node.js](https://nodejs.dev) with NPM
* [Python3](https://www.python.org) ≥ 3.7
* [pip3](https://packaging.python.org/tutorials/installing-packages/)
* [python-ldap](https://pypi.org/project/python-ldap/); To compile the Python module:
  * Debian / Ubuntu: `apt-get install libsasl2-dev python-dev libldap2-dev libssl-dev`
  * RedHat / CentOS: `yum install python-devel openldap-devel`

Check the configuration in [settings.py](settings.py). It is very short and mostly self-explaining.
Most settings can (and should) be overridden by environment variables or settings in a `.env` file; see [env.demo](env.demo) or [env.example](env.example).

## Notes

### Authentication methods

The UI always uses a simple `bind` operation to authenticate with the LDAP directory. How the `bind` DN is obtained from a given user name depends on a combination of OS environment variables, possibly from a `.env` file:

1. Search by some attribute. By default, this is the `uid`, which can be overridden by the environment variable `LOGIN_ATTR`, e.g. `LOGIN_ATTR=cn`.
2. If the environment variable `BIND_PATTERN` is set, then no search is performed. Login with a full DN can be configured with `BIND_PATTERN=%s`, which for example allows to login as user `cn=admin,dc=example,dc=org`. If a partial DN like `BIND_PATTERN=%s,dc=example,dc=org` is configured, the corresponding login would be `cn=admin`. If a specific pattern like `BIND_PATTERN=cn=%s,dc=example,dc=org` is configured, the login name is just `admin`.
3. If security is no concern, then a fixed `BIND_DN` and `BIND_PASSWORD` can be set in the environment. This is for demo purposes only, and probably a very bad idea if access to the UI is not restricted by any other means.

### Searching

Search uses a (configurable) set of criteria (`cn`, `gn`, `sn`, and `uid`) if the query does not contain `=`.
Wildcards are supported, e.g. `f*` will match all `cn`, `gn`, `sn`, and `uid` starting with `f`.
Additionally, arbitrary attributes can be searched with an LDAP filter specification, for example
`sn=F*` or `uidNumber>=100`.

### Caveats

* The software is fairly new. I use it on production directories, but you should probably test-drive it first.
* It works with [OpenLdap](http://www.openldap.org) using simple bind. Other directories have not been tested, and SASL authentication schemes are presently not supported.
* Passwords are transmitted as plain text. The LDAP server is expected to hash them (OpenLdap 2.4 does). I strongly recommend to expose the app through a TLS-enabled web server.
* HTTP *Basic Authentication* is triggered unless the `AUTHORIZATION` request variable is already set by some upstream HTTP server.

## Q&A

* Q: Why are some fields not editable?
  * A: The RDN of an entry is read-only. To change it, rename the entry with a different RDN, then change the old RDN and rename back. To change passwords, click on the question mark icon on the right side. Binary fields (as per schema) are read-only. You do not want to modify them accidentally.
* Q: Why did you write this?
  * A: [PHPLdapAdmin](http://phpldapadmin.sf.net/) has not seen updates for ages. I needed a replacement, and wanted to try Vue.

## Acknowledgements

The Python backend uses [Quart](https://pgjones.gitlab.io/quart/index.html) which is an asynchronous [Flask](http://flask.pocoo.org/). Kudos for the authors of these elegant frameworks!

The UI uses [Vue.js](https://vuejs.org) with the excellent [Bootstrap Vue](https://bootstrap-vue.js.org) components. Thanks to the authors for making frontend work much more enjoyable.
