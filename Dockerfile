FROM alpine:3
COPY ./ /src/
RUN apk add --no-cache python3 py3-pip \
    && pip3 install --break-system-packages /src \
    && apk del py3-pip \
    && rm -rf /src

HEALTHCHECK --interval=30s --timeout=2s --start-period=5s --retries=2 CMD [ "wget", "-q", "-O", "/dev/null", "http://127.0.0.1:5000" ]
EXPOSE 5000
CMD ["ldap-ui", "--host", "0.0.0.0"]
