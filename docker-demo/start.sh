#!/bin/sh

# Test to see if docker compose is installed.
if ! command -v docker-compose &> /dev/null
then
    printf "\033[1;31mError: docker-compose could not be found\033[0m\n"
    echo "Install docker-compose: https://docs.docker.com/compose/install/"
    exit
fi

cd $(dirname $0)

mkdir -p data
cp flintstones.ldif data/flintstones-data.ldif
docker-compose up -d
echo
echo "Now go to http://localhost:5000/"
