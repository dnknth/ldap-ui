# Simple LDAP editor

This is a *very minimal* web interface for LDAP directories. I wrote it over an extended weekend because I finally lost patience with [PHPLdapAdmin](http://phpldapadmin.sourceforge.net/).

Features:
* Directory tree view
* Entry creation / modification / deletion
* Schema aware
* Simple search (configurable)
* Easy to extend (less than 1000 lines of code)

## Installation and configuration

Prerequisites:
* [GNU make](https://www.gnu.org/software/make/)
* [wget](https://www.gnu.org/software/wget/)
* [Python3](https://www.python.org)
* [pip](https://packaging.python.org/tutorials/installing-packages/)
* [python-ldap](https://pypi.org/project/python-ldap/)

Download static assets into ```static/vendor``` and set up a virtual Python environment in ```venv``` with:

​    make setup

Check the configuration in `settings.py`. It is very short and should be self-explaining (Python literacy helps). 

## Usage

Run the app with

​    make run

and head over to http://localhost:5000/.

The app always requires authentication, even if the directory permits anonymous access. User credentials are validated by the LDAP directory. What a particular user can see (and edit) is governed entirely by directory access rules.

## Caveats

* The software has not been thoroughly tested. It likely has bugs. Do not use for production directories.
* It works with [OpenLdap](http://www.openldap.org) using simple authentication. Other directories and authentication schemes have not been tested.
* Currently, only plain-text is supported for new passwords. If the LDAP server does not hash them automatically, they are stored as-is.

## Acknowledgements

The Python backend uses [Flask](http://flask.pocoo.org/). Kudos for [Armin Ronacher](http://lucumr.pocoo.org) and the [other authors](http://flask.pocoo.org/docs/1.0/license/#authors) of this beautifully simple framework!

The HTML frontend uses the fantastic [Bootstrap Vue](https://bootstrap-vue.js.org) components. It was fun to write it.

## TODO

* Add support for password algorithms
* Add LDIF export / import

