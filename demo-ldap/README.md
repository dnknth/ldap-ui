# Flintstones LDAP demo

This is an [OpenLDAP](https://www.openldap.org) Docker [image](https://hub.docker.com/r/dnknth/ldap-demo)
populated with demo data of [Flintstones](https://en.wikipedia.org/wiki/The_Flintstones) characters,
courtesy of the [PHPLdapAdmin](https://phpldapadmin.sourceforge.net/) project.

To bind to the directory, use one of the following accounts:

|  DN  | Password | Role |
| ---- | -------- | ---- |
| cn=admin,o=Flintstones | bedrock | Admin |
| cn=Bamm Bamm Rubble,ou=People,o=Flintstones | bammbamm | User |
| cn=Fred Flintstone,ou=People,o=Flintstones | yabbadabbado | User |
| cn=Wilma Flintstone,ou=People,o=Flintstones | pebble | User |

Regular users can read and modify their password.
The admin modify everything.
Anonymous users can read everything except passwords.
