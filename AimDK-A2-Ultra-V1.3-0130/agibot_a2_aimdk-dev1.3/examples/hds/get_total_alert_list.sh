#!/bin/bash

# 获取系统中所有的告警（包含历史）
curl --location --request POST 'http://192.168.100.110:50587/rpc/aimdk.protocol.HDSService/GetTotalAlertList' \
     --header 'Content-Type: application/json' \
     --data-raw '{}'
