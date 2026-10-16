#!/bin/bash

# 播放某个表情
# ./a2_PlayerEmoticon.sh emoticon_id
if [ $# -eq 0 ]; then
    echo "arg error, need emoticon_id, ./a2_PlayerEmoticon.sh emoticon_id, example: "
    echo ./a2_PlayerEmoticon.sh 1
    exit 0
fi

curl -i \
    -H 'content-type:application/json' \
    -H 'timeout: 1000' \
    -X POST http://192.168.100.100:59001/rpc/aimdk.protocol.RcEmoticonPlayerService/PlayerEmoticon \
    -d '{"emoticon_id":"'$1'","is_need_data":false}'
