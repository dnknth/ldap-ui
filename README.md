# Simple LDAP editor

This is a *very minimal* web interface for LDAP directories. I wrote it over an extended weekend because I finally lost patience with [PHPLdapAdmin](http://phpldapadmin.sourceforge.net/). It may still have bugs, use with caution.

Features:
* Directory tree view
* Entry creation / modification / deletion
* Schema aware
* Simple search (configurable)
* Easy to extend (less than 1000 lines of code)

## Getting it Up and Running

Prerequisites:
* [GNU make](https://www.gnu.org/software/make/)
* [wget](https://www.gnu.org/software/wget/)
* [Python3](https://www.python.org)
* [pip](https://packaging.python.org/tutorials/installing-packages/)
* [python-ldap](https://pypi.org/project/python-ldap/)

Install them via your favourite package manager, then run.

​    make setup

This installs the static assets into ```static/vendor``` and sets up a virtual Python environment.

Adjust the configuration in `settings.py`. It should be self-explaining and is very short. Then run the app with

​    make run

and head over to http://localhost:5000/.

## Usage

The app always requires authentication, even if the directory may permit anonymous access. User credentials are validated by the LDAP directory. What a particular user can see (and edit) is governed entirely by directory access rules.

## Acknowledgements

The Python backend uses [Flask](http://flask.pocoo.org/). Kudos for [Armin Ronacher](http://lucumr.pocoo.org) and the [other authors](http://flask.pocoo.org/docs/1.0/license/#authors) of this beautifully simple web framework!

The Frontend is just one HTML page. Thanks to the fantastic [Bootstrap Vue](https://bootstrap-vue.js.org) components and [vue.js](https://vuejs.org), it was a breeze to write it.

## TODO
* Copy entries
* Add LDIF export / import
* Add password algorithms, password verification

