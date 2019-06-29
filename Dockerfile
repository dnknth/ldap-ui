FROM alpine
COPY . /app
WORKDIR /app
RUN apk add --no-cache make npm py3-pyldap \
    && make static/vendor static/node_modules \
    && pip3 install asyncio-contextmanager==1.0.1 Quart==0.6.13 \
    && apk del make npm \
    && rm -rf .git .svn .venv3
EXPOSE 5000
CMD ["/usr/bin/hypercorn", "-b", "0.0.0.0:5000", "app:app"]
