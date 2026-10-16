#!/bin/bash

curl -i     -H 'content-type:application/json' \
            -H 'timeout: 1000' \
            -X POST 'http://192.168.100.110:51011/rpc/aimdk.protocol.SystemService/GetSystemState' \
            -d '{}'