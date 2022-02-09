FROM node:lts-alpine AS builder
COPY . /app
WORKDIR /app

RUN npm update && npm run build

FROM alpine:3.15
RUN apk add --no-cache python3 py3-pip py3-pyldap py3-pytoml \
    && pip3 install 'python-dotenv==0.19.*' \
        'Hypercorn==0.12.*' 'Quart==0.16.*'

COPY . /app
COPY --from=builder /app/dist /app/dist
WORKDIR /app

EXPOSE 5000
CMD ["/usr/bin/hypercorn", "-b", "0.0.0.0:5000", "app:app"]
