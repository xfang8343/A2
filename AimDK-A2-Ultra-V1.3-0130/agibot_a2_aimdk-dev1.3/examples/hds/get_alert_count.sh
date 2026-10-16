#!/bin/bash

# 获取系统中当前存在的所有告警个数
curl --location --request POST 'http://192.168.100.110:50587/rpc/aimdk.protocol.HDSService/GetAlertCount' \
     --header 'Content-Type: application/json' \
     --data-raw '{}'