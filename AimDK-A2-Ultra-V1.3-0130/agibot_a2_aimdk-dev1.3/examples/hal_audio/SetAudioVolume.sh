#!/bin/bash

if [ $# -eq 0 ]; then
    echo "arg error, need audio_volume, ./SetAudioVolume.sh audio_volume"
    exit 0
fi

# type: SPEAKRE_BUILT_IN, SPEAKER_BLUETOOTH
curl --location --request POST 'http://192.168.100.110:56666/rpc/aimdk.protocol.HalAudioService/SetAudioVolume' \
     --header 'Content-Type: application/json' \
     --data-raw '{"audio_volume": '$1',"is_mute":false, "type": "SPEAKRE_BUILT_IN"}'
