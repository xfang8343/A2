#!/bin/bash

# 设置当前任务
curl --location --request POST 'http://192.168.100.110:57881/rpc/aimdk.protocol.TaskEngineService/SetCurrentTask' \
--header 'Content-Type: application/json' \
--data-raw '{
       "task_id": "15"
    }'

# SetCurrentTaskResponse
# {
#     "header":{
#         "code":"0",
#         "msg":"",
#         "domain":""
#     },
#     "task_id":"15",
#     "is_success":true
# }
