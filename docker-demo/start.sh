#!/bin/sh

cd $(dirname $0)

mkdir -p data
cp flintstones.ldif data/flintstones-data.ldif
docker-compose up -d
echo
echo "Now go to http://localhost:5000/"
