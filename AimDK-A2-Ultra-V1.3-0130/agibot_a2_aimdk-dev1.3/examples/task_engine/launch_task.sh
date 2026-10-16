#!/bin/bash

# 启动任务
curl --location --request POST 'http://192.168.100.110:57881/rpc/aimdk.protocol.TaskEngineService/LaunchTask' \
     --header 'Content-Type: application/json' \
     --data-raw '{
            "task_id": "15"
        }'

# LaunchTaskResponse
# {
#     "header":{
#         "code":"0",
#         "msg":""
#     },
#     "task_id":"14",
#     "res":"ReturnType_SUCCEED"
# }