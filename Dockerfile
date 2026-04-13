FROM alpine:3
RUN apk add --no-cache py3-pip py3-pyldap \
    && pip3 install --break-system-packages ldap-ui \
    && apk del py3-pip

HEALTHCHECK --interval=30s --timeout=2s --start-period=5s --retries=2 CMD [ "wget", "-q", "-O", "/dev/null", "http://127.0.0.1:5000" ]
EXPOSE 5000
CMD ["ldap-ui", "--host", "0.0.0.0"]
