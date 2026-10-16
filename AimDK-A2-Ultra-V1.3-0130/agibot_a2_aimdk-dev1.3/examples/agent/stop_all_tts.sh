#!/bin/bash

# 终止所有 TTS 播报，包括当前播报和所有队列中的任务
# ./stop_all_tts.sh

curl -i \
    -H 'content-type:application/json' \
    -X POST 'http://192.168.100.110:59301/rpc/aimdk.protocol.TTSService/StopTTS' \
    -d "{}"