#!/bin/sh
export CONFIG=/config/config.yaml
echo starting the the virtual level controller with $CONFIG
echo sleeping to allow watertank to come up
sleep 10

echo "DEBUG:"
ls -l $CONFIG
echo *****
cat $CONFIG
echo *****
ping -c 2 watertank
ping -c 2 levelcontroller

python3 virtual_controller.py --config $CONFIG