#!/bin/bash

# 0 for internal mic, 1 for external mic
curl --location --request POST 'http://192.168.100.110:59301/rpc/aimdk.protocol.AgentControlService/SetMicSourceRequest' \
     --header 'Content-Type: application/json' \
     --data-raw '{"mic_source": 1}'
