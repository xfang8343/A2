#!/bin/bash

# 播放某个动作
# ./a2_PlayerMotion.sh motion_id

if [ $# -eq 0 ]; then
    echo "arg error, need motion_id, ./a2_PlayerMotion.sh motion_id, example: "
    echo ./a2_PlayerMotion.sh 1
    exit 0
fi

curl -i \
    -H 'content-type:application/json' \
    -H 'timeout: 1000' \
    -X POST http://192.168.100.100:59001/rpc/aimdk.protocol.RcMotionPlayerService/PlayerMotion \
    -d '{"motion_id":"'$1'"}'
