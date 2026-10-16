#!/bin/bash

if [ $# -eq 0 ]; then
    echo "arg error, need text, ./tts_broadcast.sh '测试文本'"
    exit 0
fi

# 播放 tts 文本
# ./tts_broadcast.sh "测试文本"
curl -i \
    -H 'content-type:application/json' \
    -X POST 'http://192.168.100.110:59301/rpc/aimdk.protocol.TTSService/PlayTTS' \
    -d '{"text":"'$1'","priority_level":"INTERACTION_L6","domain":"example", "trace_id":"hafhjkqwjwefk", "is_interrupted":true}'
