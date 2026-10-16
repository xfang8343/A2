#!/bin/bash

curl -i \
    -H 'content-type:application/json' \
    -H 'timeout: 1000' \
    -X POST http://192.168.100.100:56444/rpc/aimdk.protocol.MotionCommandService/DisableNeckMotionPlayer \
    -d '{}'
