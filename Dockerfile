FROM alpine:3.13 AS builder
RUN apk add --no-cache alpine-sdk python3-dev py3-pip \
    && pip3 install Quart==0.6.13
    
FROM alpine:3.13
COPY --from=builder /usr/lib/python3.8/site-packages /usr/lib/python3.8/site-packages
COPY --from=builder /usr/bin/hypercorn /usr/bin/hypercorn

COPY . /app
WORKDIR /app

RUN rm -rf .git .svn .venv3 \
    && apk add --no-cache python3 py3-pyldap py3-pytoml

EXPOSE 5000
CMD ["/usr/bin/hypercorn", "-b", "0.0.0.0:5000", "app:app"]
