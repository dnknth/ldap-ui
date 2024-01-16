FROM node:lts-alpine AS builder
COPY . /app
WORKDIR /app
RUN npm audit && npm i && npm run build

FROM alpine:3
COPY --from=builder /app/dist /app/dist
RUN apk add --no-cache python3 py3-pip py3-pyldap py3-pytoml \
    && pip3 install python-dotenv Quart
COPY app.py settings.py /app/

WORKDIR /app
EXPOSE 5000
CMD ["/usr/bin/hypercorn", "-b", "0.0.0.0:5000", "--access-logfile", "-", "app:app"]
