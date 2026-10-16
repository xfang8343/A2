# A2

机器人抓取数据采集、预览与处理项目。

代码、文档、SDK、标注和处理结果随 Git 保存；完整采集数据及原始 SDK ZIP 保存在 [GitHub Release](https://github.com/xfang8343/A2/releases/tag/data-2026-10-16)。下载、恢复和校验方法见 [数据归档说明](datasets/README.md)。

## 操作记录

cd /agibot/data/home/agi/Desktop
source /opt/ros/humble/setup.bash
source /agibot/data/home/agi/Desktop/ros2_plugin_proto_aarch64/share/ros2_plugin_proto/local_setup.bash
export ROS_DOMAIN_ID=232
export ROS_LOCALHOST_ONLY=0
export FASTRTPS_DEFAULT_PROFILES_FILE=/agibot/software/v0/entry/bin/cfg/ros_dds_configuration.xml

test -r "$FASTRTPS_DEFAULT_PROFILES_FILE" && echo "DDS 配置文件可读"
ros2 daemon stop
ros2 topic list -t | grep -E '/motion/control/(arm|hand)_joint_|/aima/hal/(rgbd_camera/head_front|fish_eye_camera/chest_left)/color'


cd /home/fx/A2
python scripts/a2_bag_preview.py \
  data/grasp_data/20261008_091821_4bcb9b \
  --every 1 --stride 2

scp -o ProxyJump=agi@192.168.2.50 \
  /home/fx/A2/scripts/a2_grasp_collect.py \
  agi@192.168.100.110:/agibot/data/home/agi/Desktop/



rsync -avP --append-verify -e 'ssh -J agi@192.168.2.50' \
  agi@192.168.100.110:/agibot/data/home/agi/Desktop/grasp_data/ \
  /home/fx/A2/data/grasp_data/




cd /agibot/data/home/agi/Desktop

左臂单次抓取

python3 a2_grasp_collect.py preflight --side left --cameras head-side --visual-mode video
python3 a2_grasp_collect.py record \
  --side left --cameras head --visual-mode video \
  --task grasp_cup_left --object cup_01 --operator op_01 \
  --duration 180 --out /agibot/data/home/agi/Desktop/grasp_data/left_132


python3 a2_grasp_collect.py preflight --side left --cameras none
python3 a2_grasp_collect.py record \
  --side left --cameras none \
  --task grasp_cup_left --object cup_01 --operator op_01 \
  --duration 60 \
  --out /agibot/data/home/agi/Desktop/grasp_data/left


右臂单次抓取
python3 a2_grasp_collect.py preflight --side right --cameras head --visual-mode video
python3 a2_grasp_collect.py record \
  --side right --cameras head --visual-mode video \
  --task grasp_cup_right --object cup_01 --operator op_01 \
  --duration 180 --out /agibot/data/home/agi/Desktop/grasp_data/right_147



python3 a2_grasp_collect.py preflight --side right --cameras none

python3 a2_grasp_collect.py record \
  --side right --cameras none \
  --task grasp_cup_right --object cup_01 --operator op_01 \
  --duration 60 \
  --out /agibot/data/home/agi/Desktop/grasp_data/right






python3 a2_grasp_collect.py validate /agibot/data/home/agi/Desktop/grasp_data/left/20261008_104440_be0e77






ssh agi@192.168.2.50
ssh agi@192.168.100.110