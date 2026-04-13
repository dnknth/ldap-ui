#!/bin/sh -ex

# Restore if required
if test -e /var/restore/*data.ldif; then
    rm -rf /var/lib/openldap/*
    mkdir -p /var/lib/openldap/openldap-data
    slapadd -f /etc/openldap/slapd.conf -l /var/restore/*data.ldif
    mkdir -p /var/backups
    mv /var/restore/*data.ldif /var/backups/
fi

exec /usr/sbin/slapd -d none -h ldap:/// -f /etc/openldap/slapd.conf
