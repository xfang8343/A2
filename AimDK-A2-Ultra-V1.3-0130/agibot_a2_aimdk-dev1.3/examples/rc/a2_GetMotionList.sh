#!/bin/bash

# 获取支持播放动作的列表
# ./a2_GetMotionList.sh
curl -X POST http://192.168.100.110:51049/rpc/aimdk.protocol.ResourceService/GetMotion  \
    -H "Content-Type: application/json"   \
    -d '{}'