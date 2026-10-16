#!/bin/bash

curl -i -H "content-type:application/json" \
        -H "timeout: 60000" \
        -X POST 'http://192.168.100.110:52893/rpc/aimdk.protocol.HalRgbLightService/SetRgbLightCommand' \
        -d '{"cmd":{"red":255, "green":0, "blue":0, "effect":2, "control":1}}'
