# Simple LDAP editor

This is a *minimal* web interface for LDAP directories.

![Screenshot](screenshot.png?raw=true)

Features:

* Directory tree view
* Entry creation / modification / deletion
* LDIF import / export
* JPEG support for `inetOrgPerson`
* Schema aware
* Simple search (configurable)
* Asynchronous LDAP backend with decent scalability
* Available as [Docker image](https://hub.docker.com/r/dnknth/ldap-ui/)

The app always requires authentication, even if the directory permits anonymous access. User credentials are validated through a `bind` on the directory. What a particular user can see (and edit) is governed entirely by directory access rules. The app shows displays the directory contents, nothing less and nothing more.

## Manual installation and configuration

Prerequisites:

* [GNU make](https://www.gnu.org/software/make/)
* [Python3](https://www.python.org)
* [pip3](https://packaging.python.org/tutorials/installing-packages/)
* [python-ldap](https://pypi.org/project/python-ldap/)

To set up a virtual Python environment in `.venv3` with:

​    make setup

Check the configuration in [settings.py](settings.py). It is very short and hopefully self-explaining.

## Usage

### Standalone

Run the app with

​    make run

and head over to [http://localhost:5000/](http://localhost:5000/).

### Docker

A Dockerfile is included. The container exposes port 5000. LDAP access is controlled by these environment variables:

* `LDAP_URL`: connection URL (required), e.g. `ldap://your.ldap.server/`.
* `BASE_DN`: search base (required), e.g. `dc=example,dc=org`.
* `LOGIN_ATTR`: User name attribute (optional), defaults to `uid`.

For the impatient: Run it with

    docker run -e LDAP_URL=ldap://your.ldap.server/ -e BASE_DN=dc=example,dc=org dnknth/ldap-ui
    
For the even more impatient: A demo is provided in [docker-demo](docker-demo). Run it with

    docker-demo/start.sh

You are automatically logged in as `Fred Flintstone`.

## Caveats

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
