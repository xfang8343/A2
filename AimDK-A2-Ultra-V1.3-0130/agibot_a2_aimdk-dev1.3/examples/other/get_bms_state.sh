#!/bin/bash

# 获取电池(BMS)状态
curl -i \
    -H 'content-type:application/json' \
    -H 'timeout: 1000' \
    -X POST 'http://192.168.100.100:56421/rpc/aimdk.protocol.HalBmsService/GetBmsState' \
    -d '{}'
