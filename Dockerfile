FROM alpine:3.15

RUN apk add --no-cache python3 py3-pip py3-pyldap py3-pytoml \
    && pip3 install 'Hypercorn==0.12.*' 'Quart==0.16.*'

COPY . /app
WORKDIR /app
RUN rm -rf .git .svn .venv3

EXPOSE 5000
CMD ["/usr/bin/hypercorn", "-b", "0.0.0.0:5000", "app:app"]
