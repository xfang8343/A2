#!/bin/bash

curl -i -H "content-type:application/json" \
        -H "timeout: 60000" \
        -X POST 'http://192.168.100.100:56421/rpc/aimdk.protocol.HalRgbLightService/GetRgbLightState' \
        -d '{}'