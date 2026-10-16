#!/bin/bash

# 设置 agent 模块为 only_voice 模式，此外还有 normal（正常运行模式）, voice_face（音频输出 + 人脸识别） 模式
# 调用后需要重启 agent 进程生效（aima em stop-app agent && aima em start-app agent），后续无需重复调用
# 如果需要调整回常规状态，将其中 only_voice 改为 normal，调用后重启 agent 生效
curl -i \
    -H 'content-type:application/json' \
    -X POST 'http://192.168.100.110:59301/rpc/aimdk.protocol.AgentControlService/SetAgentPropertiesRequest' \
    -d '{ "contents": { "properties": { "2": "only_voice" } } }'
