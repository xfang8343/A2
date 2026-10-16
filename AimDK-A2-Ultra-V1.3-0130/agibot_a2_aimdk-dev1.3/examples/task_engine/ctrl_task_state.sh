#!/bin/bash

# 控制任务状态
curl --location --request POST 'http://192.168.100.110:57881/rpc/aimdk.protocol.TaskEngineService/CtrlTaskState' \
     --header 'Content-Type: application/json' \
     --data-raw '{
            "task_id": "15",
            "type" : "Type_PAUSE"
        }'


# CtrlTaskStateResponse
# {
#     "header":{
#         "code":"0",
#         "msg":""
#     },
#     "task_id":"14",
#     "res":"ReturnType_SUCCEED"
# }