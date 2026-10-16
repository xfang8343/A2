#!/bin/bash

# 屏蔽故障码
# 如果系统中某个故障码误报，可以通过此接口屏蔽该故障码，屏蔽后，该故障码将不会上报给上层。 其中:
# - `code` 为故障码，可从 `GetExceptionEvent` 接口获取，
# - `is_permanent` 为是否永久屏蔽（true: 永久屏蔽, false: 临时屏蔽,程序重启后失效），
# - `is_block` 为是否屏蔽（true: 屏蔽, false: 取消屏蔽）。
curl --location --request POST 'http://192.168.100.110:50587/rpc/aimdk.protocol.HDSService/SetShieldExceptionCode' \
     --header 'Content-Type: application/json' \
     --data-raw '{
        "code": "0x5100000005",
        "is_permanent": true,
        "is_block": true
    }'