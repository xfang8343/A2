#!/bin/bash

# 获取全量任务
curl --location --request POST 'http://192.168.100.110:57881/rpc/aimdk.protocol.TaskEngineService/GetAllTasks' \
     --header 'Content-Type: application/json' \
     --data-raw '{}'

# GetAllTasksResponse
# {
# "data": [
# {
#     "task_id": "1",
#     "name": "task1",
#     "is_valid": true,
#     "state": "StateType_IDLE",
#     "duration": "0",
#     "setting": "task_type: interaction_1 xxx YAML content"
# },
# {
#     "task_id": "2",
#     "name": "task2",
#     ...
# }
# ...
# ]}