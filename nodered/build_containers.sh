#!/bin/sh
echo Building custom nodered container
export CUR_DIR=$(pwd)

docker build -f Dockerfile.nodered -t vwt_custom_nodered:latest .
cd ..
echo building virtual_watertank containers
docker build -f Dockerfile.watertank -t watertank:latest .
docker build -f Dockerfile.levelcontroller -t levelcontroller:latest .
cd ${CUR_DIR}

echo run: 
echo docker compose -f docker-compose.nodered up 
echo     -or- 
echo docker-compose -f docker-compose.nodered up