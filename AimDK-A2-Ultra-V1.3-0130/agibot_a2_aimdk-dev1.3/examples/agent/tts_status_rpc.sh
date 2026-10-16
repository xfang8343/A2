#!/bin/bash

# 查询 tts 播报状态
# ./tts_status_rpc.sh trace_id

if [ $# -eq 0 ]; then
    echo "arg error, need trace_id, ./tts_status_rpc.sh trace_id, example: "
    echo ./tts_status_rpc.sh hafhjkqwjwefk
    exit 0
fi

curl -i \
    -H 'content-type:application/json' \
    -X POST 'http://192.168.100.110:59301/rpc/aimdk.protocol.TTSService/GetAudioStatus' \
    -d '{"trace_id":"'$1'"}'
