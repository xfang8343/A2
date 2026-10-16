#!/bin/bash

# 获取系统中的故障事件
curl --location --request POST 'http://192.168.100.110:50587/rpc/aimdk.protocol.HDSService/GetExceptionEvent' \
     --header 'Content-Type: application/json' \
     --data-raw '{}'
