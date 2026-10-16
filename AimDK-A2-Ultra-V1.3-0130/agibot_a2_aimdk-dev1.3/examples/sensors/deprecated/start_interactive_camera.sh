#!/bin/bash

cd $(dirname $0)

# detect aimrt_py installation
if ! pip show aimrt_py > /dev/null 2>&1; then
    echo "aimrt_py not installed, please install aimrt_py 1.0.0 version first"
    exit 1
fi

source /opt/ros/humble/setup.bash
export AIMRT_PLUGIN_DIR=$(pip show aimrt_py | grep Location | awk '{print $2}')/aimrt_py
source $AIMRT_PLUGIN_DIR/share/ros2_plugin_proto/local_setup.bash

python3 ./interactive_camera.py --cfg_file_path=./interactive_camera_cfg.yaml
