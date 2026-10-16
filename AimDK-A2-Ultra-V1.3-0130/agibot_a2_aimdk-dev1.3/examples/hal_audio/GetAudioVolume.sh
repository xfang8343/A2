#!/bin/bash

curl --location --request POST 'http://192.168.100.110:56666/rpc/aimdk.protocol.HalAudioService/GetAudioVolume' \
     --header 'Content-Type: application/json' \
     --data-raw '{}'