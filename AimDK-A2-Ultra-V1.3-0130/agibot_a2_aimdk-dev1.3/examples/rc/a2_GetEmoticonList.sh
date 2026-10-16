#!/bin/bash

# 获取表情列表
# ./a2_GetEmoticonList.sh
curl -X POST http://192.168.100.110:51049/rpc/aimdk.protocol.ResourceService/GetEmoticon  \
    -H "Content-Type: application/json"   \
    -d '{}'
