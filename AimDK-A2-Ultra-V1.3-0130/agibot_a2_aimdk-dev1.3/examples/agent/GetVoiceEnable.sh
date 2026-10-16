#!/bin/bash

curl --location --request POST 'http://192.168.100.110:59301/rpc/aimdk.protocol.AgentControlService/GetVoiceEnable' \
     --header 'Content-Type: application/json' \
     --data-raw '{}'
