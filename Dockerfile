FROM alpine
COPY . /app
WORKDIR /app
RUN apk add --no-cache py3-pyldap \
    && pip3 install Quart==0.6.13 \
    && rm -rf .git .svn .venv3
EXPOSE 5000
CMD ["/usr/bin/hypercorn", "-b", "0.0.0.0:5000", "app:app"]
