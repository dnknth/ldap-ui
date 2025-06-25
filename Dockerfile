FROM alpine:3
RUN apk add --no-cache py3-pip py3-pyldap \
    && pip3 install --break-system-packages ldap-ui \
    && apk del py3-pip

EXPOSE 5000
CMD ["ldap-ui", "--host", "0.0.0.0"]
