#!/bin/bash

# 1. 要注册的 images 目录（sh脚本同级）
RUN_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGES_DIR="${RUN_SCRIPT_DIR}/images"

# 2. Faceid base目录
FACEID_SCRIPT_DIR="/agibot/software/v0/scripts/agent/face_id/"
FACEID_LIB_DIR="/agibot/software/v0/bin"
FACEID_OFFLINE_FEAT="/agibot/data/param/interaction/face_id/offline_face_features"

# 3. 可执行文件与配置文件的相对路径
EXEC="${FACEID_SCRIPT_DIR}/face_id_register"
CONF="${FACEID_SCRIPT_DIR}/face_id_config.json"

chmod +x "$EXEC"
export LD_LIBRARY_PATH="${FACEID_LIB_DIR}":$LD_LIBRARY_PATH

# 4. 调用
rm -rf "$FACEID_OFFLINE_FEAT"/*
"$EXEC" "$CONF" "$IMAGES_DIR"
