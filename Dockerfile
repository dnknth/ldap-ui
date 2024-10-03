FROM node:lts-alpine AS builder
COPY . /app
WORKDIR /app
RUN npm audit && npm i && npm run build

FROM alpine:3
COPY --from=builder /app/dist /app/dist
RUN apk add --no-cache python3 py3-pip py3-pyldap py3-pytoml \
    && pip3 install --break-system-packages python-multipart starlette uvicorn
COPY app.py ldap_api.py ldap_helpers.py schema.py settings.py /app/

WORKDIR /app
EXPOSE 5000
CMD ["/usr/bin/uvicorn", "--host", "0.0.0.0", "--port", "5000", "app:app"]
