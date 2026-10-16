#!/bin/bash

# 尝试清除当前的告警
# 清除告警前，需要先获取到告警的 id， 可以通过 GetAlertList 获取到告警的 id。此接口为尝试清除告警，如果告警清除后，继续上报，则清除失败。
curl --location --request POST 'http://192.168.100.110:50587/rpc/aimdk.protocol.HDSService/ClearAlert' \
     --header 'Content-Type: application/json' \
     --data-raw '{"id":"d0062056-1d4f-43ec-a36c-18fc149a5781"}'