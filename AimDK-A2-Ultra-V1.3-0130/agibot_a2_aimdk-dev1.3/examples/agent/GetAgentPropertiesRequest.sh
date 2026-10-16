#!/bin/bash

# 获取 agent 模块的属性
curl -i \
    -H 'content-type:application/json' \
    -X POST 'http://192.168.100.110:59301/rpc/aimdk.protocol.AgentControlService/GetAgentPropertiesRequest' \
    -d '{"property_ids": [2]}'
