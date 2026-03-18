#!/bin/sh
docker build -t levelcontroller .

echo "to run container:"
echo "  docker run --rm -p 5051:5051 levelcontroller"
