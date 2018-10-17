# Simple LDAP editor

This is a *very minimal* web interface for LDAP directories. 

Features:
* Directory tree view
* Entry creation / modification / deletion
* Schema aware
* Simple search (configurable)
* Available as [Docker image](https://hub.docker.com/r/dnknth/ldap-ui/)

The app always requires authentication, even if the directory permits anonymous access. User credentials are validated against the LDAP directory. What a particular user can see (and edit) is governed entirely by directory access rules.

## Manual installation and configuration

Prerequisites:
* [GNU make](https://www.gnu.org/software/make/)
* [wget](https://www.gnu.org/software/wget/)
* [Python3](https://www.python.org)
* [pip](https://packaging.python.org/tutorials/installing-packages/)
* [python-ldap](https://pypi.org/project/python-ldap/)

Download static assets into ```static/vendor``` and set up a virtual Python environment in ```venv``` with:

​    make setup

Check the configuration in [settings.py](settings.py). It is very short and should be self-explaining. 

## Usage

### Standalone

Run the app with

​    make run

and head over to http://localhost:5000/.

### Docker

A Dockerfile is included. The container exposes port 5000. LDAP access is controlled by these environment variables:

* `LDAP_URL`: connection URL, e.g. `ldap://your.ldap.server/`, defaults to `ldap:///`
* `BASE_DN`: search base, e.g. `dc=example,dc=org`. This one is required.
* `LOGIN_ATTR`: User name attribute, defaults to `uid`

## Caveats

* The software has not been tested extensively. Do not use for production directories (like I do).
* It works with [OpenLdap](http://www.openldap.org) using simple authentication. Other directories have not been tested, and other authentication schemes are currently not supported.
* Passwords are transmitted as plain text. The LDAP server is expected to hash them (like OpenLdap 2.4 does).
* The app will trigger a HTTP Basic authentication unless the `AUTHORIZATION` request variable has been set by some upstream web server. 

## Q&A
* Q: Why are some fields not editable?
  * A: The RDN of an entry is read-only. To change it, rename the entry with a different RDN, then change the old RDN and rename back. To change passwords, click on the question mark icon on the right side.

## Acknowledgements

The Python backend uses [Flask](http://flask.pocoo.org/). Kudos for [Armin Ronacher](http://lucumr.pocoo.org) and the [other authors](http://flask.pocoo.org/docs/1.0/license/#authors) of this elegant framework!

The  frontend uses [Vue.js](https://vuejs.org) with the fantastic [Bootstrap Vue](https://bootstrap-vue.js.org) components. Thanks to the authors for taking a lot of pain out of HTML.

## TODO

* Add LDIF export / import
* Add support for images (i.e inetOrgPerson)

