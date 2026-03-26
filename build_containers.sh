#!/bin/sh
echo Building two docker containers
export CUR_DIR=$(pwd)

docker build -f Dockerfile.watertank -t watertank:latest .
docker build -f Dockerfile.levelcontroller -t levelcontroller:latest .

echo run 'docker compose up' or 'docker-compose up'
