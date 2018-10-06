FROM alpine
COPY . /app
WORKDIR /app
RUN apk add --no-cache make py3-pyldap wget \
    && make static/vendor \
    && pip3 install Flask==1.0.2 gunicorn==19.9.0 \
    && apk del --no-cache make wget \
    && rm -rf .git .svn .venv3
EXPOSE 5000
CMD ["/usr/bin/gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "app:app"]
