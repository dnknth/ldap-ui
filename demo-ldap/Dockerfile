FROM alpine

RUN apk add --no-cache openldap openldap-clients openldap-back-mdb
COPY slapd.conf /etc/openldap/slapd.conf
COPY flintstones.ldif /var/restore/flintstones-data.ldif
COPY start.sh /start.sh

HEALTHCHECK --interval=30s --timeout=2s --start-period=5s --retries=2 CMD [ "ldapsearch", "-LLLx", "-b", "o=Flintstones", "cn=admin", "dn" ]
EXPOSE 389
CMD [ "/start.sh" ]
