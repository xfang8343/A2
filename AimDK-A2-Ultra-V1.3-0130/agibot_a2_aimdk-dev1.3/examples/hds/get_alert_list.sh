#!/bin/bash

# 获取当前的告警列表
curl --location --request POST 'http://192.168.100.110:50587/rpc/aimdk.protocol.HDSService/GetAlertList' \
     --header 'Content-Type: application/json' \
     --data-raw '{}'
