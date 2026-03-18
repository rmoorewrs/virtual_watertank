#!/bin/sh
echo Building two docker containers
export CUR_DIR=$(pwd)

cd ${CUR_DIR}/src/virtual_watertank
docker build -t watertank .

cd ${CUR_DIR}/src/virtual_levelcontroller
docker build -t levelcontroller .
cd ${CUR_DIR}

echo docker compose up