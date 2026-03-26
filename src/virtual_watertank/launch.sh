#!/bin/sh
export CONFIG=/config/config.yaml
echo starting the virtual watertank with $CONFIG

echo "DEBUG:"
ls -l $CONFIG
echo *****
cat $CONFIG
echo *****
ping -c 2 watertank
ping -c 2 levelcontroller

python3 virtual_watertank.py --config $CONFIG