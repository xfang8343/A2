#!/bin/bash

# 获取已存储的地图列表
curl --location --request POST 'http://192.168.100.110:50807/rpc/aimdk.protocol.MappingService/GetStoredMapNames' \
     --header 'Content-Type: application/json' \
     --data-raw '{"header":{},"command":"MappingCommand_GET_STORED_MAP_NAME"}'
