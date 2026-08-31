# A fast and versatile LDAP editor

[![Docker](https://img.shields.io/docker/v/dnknth/ldap-ui?label=Docker&logo=docker)](https://hub.docker.com/r/dnknth/ldap-ui)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

This is a *minimal* web interface for LDAP directories. Docker images for `linux/amd64` and `linux/arm64/v8` are [available](https://hub.docker.com/r/dnknth/ldap-ui).

![Screenshot](https://github.com/dnknth/ldap-ui/blob/main/screenshot.png?raw=true)

## Features:

- Directory tree view
- Entry creation / modification / deletion
- LDIF import / export
- Image support for the `jpegPhoto` and `thumbnailPhoto` attributes
- Schema aware
- Simple search (configurable)
- Asynchronous LDAP backend with decent scalability
- Available as [Docker image](https://hub.docker.com/r/dnknth/ldap-ui)

The app always requires authentication, even if the directory permits anonymous access. Credentials are validated through a simple `bind` on the directory (SASL is not supported). What a user can see and edit is governed entirely by directory access rules.

## Usage


### Docker

For the impatient: Run it with

```shell
docker run -p 127.0.0.1:5000:5000 \
    -e LDAP_URL=ldap://your.openldap.server/ \
    dnknth/ldap-ui:latest
```

For the even more impatient: Start a demo with

```shell
docker compose up -d
```

then go to <http://localhost:5000/> and log in with one of the following accounts:

| UID     | Password       | Role                              |
| ------- | -------------- | --------------------------------- |
| `admin` | `bedrock`      | Admin (full access)               |
| `fred`  | `yabbadabbado` | User (read + self-password-write) |

### Pip

Install `ldap-ui` in a virtual environment:

```shell
python3 -m venv .venv
source .venv/bin/activate
pip3 install ldap-ui
```

After a shell `rehash` (if needed), the command `ldap-ui` becomes available:

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

### Environment variables

LDAP access is controlled by the following optional environment variables, possibly from a `.env` file:

- `LDAP_URL`: Connection URL in RFC 4516 format, defaults to `ldap:///`.
- `BASE_DN`: Optional search base, e.g. `dc=example,dc=org`, can also be specified as part of the `LDAP_URL`.
- `SCHEMA_DN`: Optional DN to obtain the directory schema, e.g. `cn=subSchema`.
- `LOGIN_ATTR`: User name attribute, defaults to `uid`.
- `USE_TLS`: Enable TLS, defaults to true for `ldaps` connections. Set it to a non-empty string to force `STARTTLS` on `ldap` connections.

If `BASE_DN` or `SCHEMA_DN` are not provided explicitly, auto-detection from the root DSA is attempted.
For this, the root DSA must be readable anonymously, e.g. with the following ACL line for OpenLDAP:

```text
access to dn.base="" by * read
```

For finer-grained control, see [settings.py](settings.py).

## Development

Prerequisites:

- [node.js](https://nodejs.dev) LTS version with NPM
- [pnpm](https://pnpm.io)
- [Python](https://www.python.org) ≥ 3.10
- [uv](https://docs.astral.sh/uv/)
- [GNU make](https://www.gnu.org/software/make/)

`ldap-ui` consists of a Vue frontend and a Python backend that translates a subset of the LDAP protocol to a stateless ReST API.

`pnpm build` assembles the frontend in `backend/ldap_ui/statics`.

Review the configuration in [settings.py](settings.py); it is short and mostly self-explanatory (also see notes below). Most settings can be overridden by environment variables or settings in a `.env` file.

Run the backend locally:

- `make` — installs dependencies, builds the frontend if needed, and starts the server.
- `make debug` — starts the server in reload mode on port 5000 with `DEBUG=true`.

The frontend can be developed independently with hot-reload support using `pnpm dev`.

## Notes

### Authentication methods

The UI always uses a simple `bind` operation to authenticate with the LDAP directory. How the `bind` DN is obtained from a given user name depends on a combination of OS environment variables, possibly from a `.env` file:

1. Search by some attribute. By default this is `uid` (overridable via `LOGIN_ATTR`, e.g. `LOGIN_ATTR=cn`). The search is anonymous, so the directory must grant anonymous read access to the search attribute within the search base. To avoid that, use `BIND_PATTERN` (item 2) or require a full-DN login.
2. If `BIND_PATTERN` is set, no search is performed. `BIND_PATTERN=%s` requires a full DN (e.g. login `cn=admin,dc=example,dc=org`); `BIND_PATTERN=%s,dc=example,dc=org` allows `cn=admin`; `BIND_PATTERN=cn=%s,dc=example,dc=org` allows `admin`.

### Searching

Search uses a configurable set of criteria (default: `cn`, `gn`, `sn`, and `uid`) if the query does not contain `=`. Wildcards are supported, e.g. `f*` matches all `cn`, `gn`, `sn`, and `uid` starting with `f`. Arbitrary attributes can also be searched with an LDAP filter, e.g. `sn=F*`.

Apart from the search field in the navigation bar, searches are also performed in the entry editor for any DN-valued input field.

### Keyboard navigation

The editor and modal dialogs focus the first input when opening, so you can use the ⇥ key to navigate the form.
Save or dismiss with the ↩ key.

The following [access keys](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Global_attributes/accesskey#try_it) are defined:

| Access Key | UI Element                |
|------------|---------------------------|
| K          | Global search at page top |
| A          | Add an attribute           |
| O          | Add an object class       |
| R          | Reset entry modifications |
| S          | Save an entry (same as ↩) |

### Caveats

- The software works with [OpenLDAP](http://www.openldap.org) using simple bind. Other directories have not been tested much, although [389 DS](https://www.port389.org) works to some extent.
- SASL authentication schemes are presently not supported.
- Passwords are transmitted as plain text. The LDAP server is expected to hash them (OpenLDAP 2.4 does). I strongly recommend exposing the app through a TLS-enabled web server.
- HTTP *Basic Authentication* is performed by the app: the login dialog collects credentials and a request interceptor (`src/auth.ts`) attaches `Authorization: Basic` to every request once logged in. On startup the app probes `/api/whoami`; if an upstream HTTP server (or a native browser Basic challenge) already supplied the `AUTHORIZATION` request variable, the session is treated as authenticated and the login dialog is skipped. Otherwise the dialog credentials are used, replacing any upstream-provided header.
- LDIF export never includes plaintext passwords: `userPassword` values without an RFC&nbsp;2307 scheme prefix (`{SSHA}`, `{SHA}`, `{MD5}`, …) — or explicitly marked `{CLEARTEXT}`/`{PLAIN}` — are omitted even when the *Include sensitive (hashed passwords)* option is enabled (`?include_sensitive=true`). Only hashed values with a scheme prefix can be exported, so a directory that stores passwords in plaintext cannot leak them through an export.

## Q&A

- Q: Why are some fields not editable?
  - A: The RDN of an entry is read-only. To change it, rename the entry with a different RDN, then change the old RDN and rename back. To change passwords, click on the question mark icon on the right side. Binary fields (as per schema) are read-only. You do not want to modify them accidentally.
- Q: Why did you write this?
  - A: [PHPLdapAdmin](http://phpldapadmin.sf.net/) is no longer actively maintained. I needed a replacement, and wanted to try Vue.

## Acknowledgements

The Python backend uses [FastAPI](https://fastapi.tiangolo.com). The UI is built with [Vue.js](https://vuejs.org) and [Tailwind CSS](https://tailwindcss.com/). Kudos to the authors of these elegant frameworks!
