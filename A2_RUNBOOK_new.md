# A2 联调 Runbook

> 原测试目录在本次开始时仅保留了本 Runbook。下文早期测试所列的 `a2_collect_remote.py`、
> `record_rosbag.sh` 等脚本及 AimDK 安装包并不在本目录中；这些命令是历史记录，
> 不能直接在当前目录执行。新的上肢抓取数采入口见下一节。

## 上肢抓取动作数采（AimDK v1.3）

新脚本：`scripts/a2_grasp_collect.py`。它只订阅 ROS2 Topic 并调用 `ros2 bag record`，
不会切换 Action 或给机器人发动作。示教动作需由已验证的官方遥操/控制链路产生。
默认录制手臂、手指状态和头部/胸部三路 RGB；`--depth` 再加入头部深度图。
发现的 `/motion/control/*_joint_command`、`/rc/command`、`/rc/virtual/*`、
`/rc/data/pb_*` 会一并录制。正式数采默认要求至少有命令 Topic，录后也要求有实际命令消息。
若 `ros2 interface show ros2_plugin_proto/msg/RosMsgWrapper` 报 Unknown package，
先加载 AimDK ARM64 的 `ros2_plugin_proto/local_setup.bash`；也可加 `--skip-proto`
仅采集标准上肢命令话题，并在录后确认确有命令消息。

按官方 v1.3 的部署要求，在机器人 ORIN 的 `/agibot/data/home/agi/Desktop`
运行并保存数据，先加载 ROS2 和 DDS 环境：

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=232
export ROS_LOCALHOST_ONLY=0
export FASTRTPS_DEFAULT_PROFILES_FILE=/agibot/software/v0/entry/bin/cfg/ros_dds_configuration.xml
# 如果需要录制 AimDK 的 proto wrapper Topic，还需加载 SDK 包中的消息定义：
# source <AimDK解压目录>/prebuilt/ros2_plugin_proto_aarch64/share/ros2_plugin_proto/local_setup.bash
```

把 `scripts/a2_grasp_collect.py` 复制到 ORIN 后，先检查话题；视频模式还需同目录的 `a2_video_recorder.py`：

```bash
python3 a2_grasp_collect.py preflight
```

开始单次示教；每次运行生成独立目录和 `bag/`、`manifest.json`、`recorder.log`：

```bash
python3 a2_grasp_collect.py record \
  --task grasp_cup --object cup_01 --operator op_01 \
  --duration 60 --out /agibot/data/home/agi/Desktop/grasp_data
```

抓取完成后，根据脚本打印出的单次目录标注和复核：

```bash
python3 a2_grasp_collect.py label /path/to/session --outcome success --notes "抓住杯柄"
python3 a2_grasp_collect.py validate /path/to/session
```

若只想验证相机与关节状态链路，可在 `preflight` / `record` 后加
`--allow-state-only`。这类数据没有命令标签，不能直接当成动作示教样本。
手部位置在 A2 文档中是 0–2000 的无单位抽象值；腕部 6/7 轴是并联机构
映射后的等效串联角，后续转模型动作前需按真实 Topic 字段标定。
如果示教通过 HTTP RPC 而非 ROS2 Topic 下发，仅录包无法保留动作命令，
需另行记录 RPC 请求及其时间戳并与本包对齐。

官方接口依据：[ROS2 通信与 QoS](https://open.agibot.com/docs/aimdk/a2/v1_3/dev_guide/03-second_develop_interface_overview)、
[手臂及手指 Topic](https://open.agibot.com/docs/aimdk/a2/v1_3/dev_guide/07-01-motion_control)、
[相机 Topic](https://open.agibot.com/docs/aimdk/a2/v1_3/dev_guide/07-04-sensor_data)。

## 左臂、右臂任务分开采集

更新后的脚本提供 `--side left|right|both|none` 和
`--cameras all|head-side|head|side|none`。默认 `both/all` 保持原三路 RGB。
`--side none` 表示不指定任务侧；配合 `head-side` 时只录头相机，配合 `side` 时不录相机。
`--cameras none` 表示不录任何相机，不能同时加 `--depth`。
A2 的 `/motion/control/arm_joint_*` 和 `/motion/control/hand_joint_*` 各是一条双侧
`JointState` 话题，`--side` 记录任务侧并用于相机选择；原始 bag 仍保存双侧关节，
后处理时按关节名称筛选左侧或右侧。关节数据很小，保留另一侧也可检查误动作。

左臂示教（头相机 + 左胸相机）：

```bash
python3 a2_grasp_collect.py preflight --side left --cameras head-side
python3 a2_grasp_collect.py record --side left --cameras head-side \
  --task grasp_cup_left --object cup_01 --operator op_01 --duration 60 \
  --out /agibot/data/home/agi/Desktop/grasp_data/left
```

右臂示教（头相机 + 右胸相机）：

```bash
python3 a2_grasp_collect.py preflight --side right --cameras head-side
python3 a2_grasp_collect.py record --side right --cameras head-side \
  --task grasp_cup_right --object cup_01 --operator op_01 --duration 60 \
  --out /agibot/data/home/agi/Desktop/grasp_data/right
```

完全不录相机时，单侧抓取命令如下；这仍会录制双侧关节话题，`side` 写入本次任务标签：

```bash
python3 a2_grasp_collect.py preflight --side left --cameras none
python3 a2_grasp_collect.py record --side left --cameras none \
  --task grasp_cup_left --object cup_01 --operator op_01 --duration 60 \
  --out /agibot/data/home/agi/Desktop/grasp_data/left

python3 a2_grasp_collect.py preflight --side right --cameras none
python3 a2_grasp_collect.py record --side right --cameras none \
  --task grasp_cup_right --object cup_01 --operator op_01 --duration 60 \
  --out /agibot/data/home/agi/Desktop/grasp_data/right
```

历史样本约 53 秒，头部 RGB 占 2.021 GiB，胸部左右各 1.37 GiB；
选择 `head-side` 预计同等时长约 3.4 GiB，节省约 1.37 GiB。
只选 `side` 预计约 1.4 GiB；`none` 仅保留关节和命令，不适合视觉抓取模型。
若后续沿用 GO-1 Air 的三相机输入，继续用 `--cameras all`。

## 视频数采（Diffusion Policy 数据准备）

视频模式将相机 ROS2 `Image` 实时编码为 H.264 MP4，每路另存
`*_timestamps.csv`（帧序号、ROS 消息时间戳、接收时间戳）。
`bag/` 仍保存双臂、双手关节状态与命令及在线的遥操话题；
`--visual-mode video` 不把 RGB 原始 `Image` 写入 bag，也不生成逐帧图片。
`--visual-mode images` 是旧行为，保留原始图像话题；`both` 同时保存原始图像
和视频；`none` 完全不录视觉数据。相机组合仍由
`--cameras all|head-side|head|side|none` 指定；任务侧仍由
`--side left|right|both|none` 标注。关节话题本身包含双侧，转换训练集时按
`JointState.name` 选择目标侧。

从本机复制**两个**脚本到 ORIN（按当前两级 SSH 路径）：

```bash
scp -o ProxyJump=agi@192.168.2.50 \
  /home/fx/A2/scripts/a2_grasp_collect.py \
  /home/fx/A2/scripts/a2_video_recorder.py \
  agi@192.168.100.110:/agibot/data/home/agi/Desktop/
```

在 ORIN 终端加载前述 ROS2/DDS 环境和 `ros2_plugin_proto` 消息包。
视频模式还要求 `ffmpeg` 包含 `libx264`、Python 可导入 `rclpy` 和
`sensor_msgs`。ORIN 若提示“缺少 ffmpeg”，在 ORIN 安装并验证：

```bash
sudo apt-get update
sudo apt-get install ffmpeg
ffmpeg -hide_banner -encoders | grep libx264
```

应看到 `libx264` 编码器，然后运行 preflight；它会检查这些依赖。
如果 `apt-get install ffmpeg` 提示 `unmet dependencies` 或
`apt --fix-broken install`，先运行
`apt-get -s -f install`、
`apt-cache policy ffmpeg libsrt1.4-openssl libbluetooth-dev libbluetooth3`
与 `apt-mark showhold` 查看计划改动和候选版本，再处理包冲突；
不要在不了解模拟结果时直接修复机器人系统的软件包。
本机 2026-10-08 的模拟结果为只升级 `libbluetooth3`
`5.64-0ubuntu1.1 → 5.64-0ubuntu1.4`，`0 to remove`；
`apt-mark showhold` 仅列出 `python3`、`python3-pip`。
在该结果未变化时，可先运行 `sudo apt-get -f install`，
再运行 `sudo apt-get install ffmpeg`；安装后检查 `libx264`。
A2 v1.3 官方的 `/color/h264` 是实验性 5 Hz 接口；当前脚本使用
15 Hz 头部原始流、30 Hz 胸部原始流来生成视频，避免降到 5 Hz。
[相机频率依据](https://open.agibot.com/docs/aimdk/a2/v1_3/dev_guide/07-04-sensor_data)。

```bash
cd /agibot/data/home/agi/Desktop
source /opt/ros/humble/setup.bash
source /agibot/data/home/agi/Desktop/ros2_plugin_proto_aarch64/share/ros2_plugin_proto/local_setup.bash
export ROS_DOMAIN_ID=232
export ROS_LOCALHOST_ONLY=0
export FASTRTPS_DEFAULT_PROFILES_FILE=/agibot/software/v0/entry/bin/cfg/ros_dds_configuration.xml
python3 a2_grasp_collect.py preflight --side left --cameras head-side --visual-mode video
```

左臂单次抓取，头部 + 左胸视频：

```bash
python3 a2_grasp_collect.py record \
  --side left --cameras head-side --visual-mode video \
  --task grasp_cup_left --object cup_01 --operator op_01 \
  --duration 60 --out /agibot/data/home/agi/Desktop/grasp_data/left
```

右臂单次抓取，头部 + 右胸视频：

```bash
python3 a2_grasp_collect.py preflight --side right --cameras head-side --visual-mode video
python3 a2_grasp_collect.py record \
  --side right --cameras head-side --visual-mode video \
  --task grasp_cup_right --object cup_01 --operator op_01 \
  --duration 60 --out /agibot/data/home/agi/Desktop/grasp_data/right
```

仅录关节与在线遥操时用 `--cameras none`，可搭配默认
`--visual-mode images` 或明确指定 `--visual-mode none`。
`--side none` 表示不指定任务侧；`--cameras head-side` 此时只选头相机，
`--cameras side` 此时无相机。视频结束后检查脚本打印的目录：

```bash
python3 a2_grasp_collect.py validate /path/to/session
python3 a2_grasp_collect.py label /path/to/session --outcome success
```

预期目录包括 `bag/`、`video/head.mp4`、`video/chest_left.mp4`
或 `video/chest_right.mp4`、相应的 `*_timestamps.csv`、
`video/summary.json`、`manifest.json` 与两个录制日志。
MP4 按固定帧率播放，训练对齐以 CSV 中逐帧时间戳为准。
此脚本使用 ffmpeg 的 `libx264` 实时编码；首次正式数采先做短时试录，
检查 `validate` 中各路帧数、丢帧数和视频可播放性。
Diffusion Policy 训练入口通常需要按时间轴对齐的视频帧、状态和动作数组，
不能直接把 MP4 和 bag 目录交给训练脚本；后续转换时再按侧别筛选关节并
构建所选训练配置的数据集。

## 本机查看录包与后处理

完整传回本机后，确认 `bag/bag_0.db3` 和 `bag/metadata.yaml` 都存在；
若只看到 `.bag_0.db3.*`，表示 rsync 仍在传输。无需连接机器人，直接生成
相机抽帧预览和关节命令/状态的数值范围：

```bash
python scripts/a2_bag_preview.py data/grasp_data/<采集目录> --every 5 --stride 2
```

该命令适用于 `--visual-mode images/both` 的原始相机话题；
视频模式的 bag 不含相机图像，视频请直接查看 `video/*.mp4` 与
`video/*_timestamps.csv`。
在浏览器打开 `<采集目录>/preview/index.html` 查看三路相机每 5 秒的画面；
`preview/joint_ranges.csv` 展示每个关节在整包内的命令和反馈范围；
`preview/joint_trace_10hz.csv` 是约 10 Hz 的关节命令/状态时间序列，可用于画曲线。
该工具只读 SQLite，不发布 ROS2 Topic。原始 bag、`manifest.json`、
`qos.yaml` 和 `recorder.log` 一起保留，后续按任务需要另做时间对齐和训练格式转换。

本次 `20261008_091821_4bcb9b` 包：约 53.32 秒，左臂和左手有明显动作，右臂右手基本静止；
`/rc/data/...RemoteControlChannel` 为 0 条，实际可用的动作标签是
`/motion/control/arm_joint_command` 与 `/motion/control/hand_joint_command`。

## 环境

```bash
conda activate agi
```

本机已准备：

- AimDK SDK：`agibot_a2_aimdk-dev1.3`
- GO-1 代码：`third_party/AgiBot-World`
- GO-1 Air 权重：`models/GO-1-Air`
- 机器人：`10.10.60.24`
- SSH：`agi` / `1`

重建环境：

```bash
bash scripts/install_agi_env.sh
```

## 只读采样

本机触发机器人采集：

```bash
python scripts/a2_collect_remote.py --seconds 10 --rate 1 --images go1 --out data/a2_samples
```

校验样本：

```bash
python scripts/check_a2_sample.py data/a2_samples/<run>/a2_collect_<run>/samples.jsonl
```

当前已验证：

- HTTP：`BMS/action/joint/hand/neck`
- ROS：`/motion/control/arm_joint_state`、`/motion/control/hand_joint_state`、`/body_drive/imu/data`
- 图像 topic 存在：头部 RGB-D、腰部 RGB-D、胸部左右鱼眼、交互相机
- 已修复采集默认值：`--images go1` 只抓 `head_color/chest_left/chest_right`，避免全量图像和点云把头相机挤掉
- 如需全量图像，用 `--images all`；如需点云，额外加 `--lidar`
- 时间戳单调，GO-1 状态维度为 `[1,16]`

GO-1 默认输入映射：

```text
top   <- head_color；无帧时 fallback 到 waist_color/chest_left
right <- chest_right
left  <- chest_left
state <- 左臂 7 关节 + 左手平均开合 + 右臂 7 关节 + 右手平均开合
freq  <- 30
```

正式采集时建议加 `--strict-images` 检查三路图是否按原始映射到齐。

## 左手/左臂小动作

默认只检查状态，不下发：

```bash
python scripts/left_arm_hand_micro.py --duration 60
```

现场确认后再执行：

```bash
python scripts/left_arm_hand_micro.py \
  --execute \
  --set-action McAction_RL_LOCOMOTION_ARM_EXT_JOINT_SERVO \
  --duration 60 \
  --elbow-amp 0.015 \
  --wrist-amp 0.0 \
  --torque 100
```

再尝试腕部：

```bash
python scripts/left_arm_hand_micro.py \
  --execute \
  --set-action McAction_RL_LOCOMOTION_ARM_EXT_JOINT_SERVO \
  --duration 60 \
  --elbow-amp 0.03 \
  --wrist-amp 0.015 \
  --torque 120
```

说明：

- `McAction_DEFAULT` 下 `JointControl` 会返回 500
- 腕部对应左臂第 6/7 轴：`idx18_left_arm_joint6`、`idx19_left_arm_joint7`
- 手指用 HTTP `SetHandCommand`
- 左臂/腕用 ROS2 `/motion/control/arm_joint_command`

## 官方遥操套件

SDK 里有官方遥操协议：

- `QuestProVrController`
- `UniversalGamepad`
- `AimMasterControl`
- `RemoteControlMode_UPPER_BODY`
- `/rc/virtual/joint_states`
- `/rc/virtual/joint_states_change`
- `/rc/virtual/joint_descarts_change`

A2 足式上肢 joint id：

```text
15-21  左臂 LAJ1-LAJ5 + LWJ1/LWJ2
22-28  右臂 RAJ1-RAJ5 + RWJ1/RWJ2
29-34  左手 6 关节
35-40  右手 6 关节
```

设备到货后先跑：

```bash
python scripts/a2_teleop_ready.py --out data/teleop_ready
```

当前未接设备时实测：

- 有：`/motion/control/arm_joint_state`
- 未在线：`/rc/*`、`/motion/control/arm_joint_command`、`/motion/control/hand_joint_command`

看到遥操输入/上肢命令 topic 后录包：

```bash
bash scripts/record_rosbag.sh \
  --duration 300 \
  --out data/rosbags/teleop_001 \
  --topics /rc/command,/rc/virtual/joint_states,/motion/control/arm_joint_state,/motion/control/hand_joint_state,/aima/hal/rgbd_camera/head_front/color,/aima/hal/fish_eye_camera/chest_left/color,/aima/hal/fish_eye_camera/chest_right/color
```

如果套件发布的是 proto wrapper topic，把 `a2_teleop_ready.py` 打印出的 `/rc/data/pb_*` 或 `QuestPro/AimMaster` topic 加进 `--topics`。

## GO-1 Air

权重检查：

```bash
python scripts/go1_air_infer.py --model models/GO-1-Air
```

本机 smoke 推理：

```bash
python scripts/go1_air_infer.py --model models/GO-1-Air --smoke
```

启动官方推理服务：

```bash
PYTHONPATH=third_party/AgiBot-World python third_party/AgiBot-World/evaluate/deploy.py \
  --model_path models/GO-1-Air \
  --host 127.0.0.1 \
  --port 9000
```

用 A2 采样调用 GO-1：

```bash
python scripts/go1_a2_client.py \
  data/a2_samples/<run>/a2_collect_<run>/samples.jsonl \
  --instruction "pour water into the cup" \
  --server http://127.0.0.1:9000
```

动作适配检查：

```bash
python scripts/go1_adapter_check.py \
  data/a2_samples/<run>/a2_collect_<run>/samples.jsonl \
  --instruction "pour water into the cup" \
  --server http://127.0.0.1:9000
```

指定任务就改 `--instruction`，例如：

```bash
--instruction "pick up the bottle and pour water into the cup"
--instruction "grasp the cup handle and place it on the tray"
```

当前只开放推理，不直接下发 GO-1 动作到 A2。原因是 GO-1 Air 输出 `[30,16]` 动作块，但 A2 的真实上肢命令需要标定动作维度、关节顺序、单位、限幅和安全停止。未标定前，`scripts/go1_a2_client.py --execute` 会拒绝执行。

当前 adapter 设定见 `config/go1_a2_adapter.json`：

- 动作顺序：`左臂7 rad + 左手开合1 + 右臂7 rad + 右手开合1`
- 单位：手臂按绝对关节 rad；手部按 `0-1` 平均开合，执行前 clamp 后映射到 A2 手指 `500-1000`
- 速率：模型 `ctrl_freq=30`，发布频率先设 30Hz，默认每 10 步重规划
- 限幅：按吊挂演示小工作空间设置，不是机械极限
- 停止：进程退出/异常时发布保持或回中，手部松开，必要时切回安全 action
- 相机：正式跑前用 `--strict-images` 确认 `head_color/chest_right/chest_left` 都稳定

已验证：

- CUDA：RTX 5070 Ti 可用
- GO-1 Air 输出：`[30,16]`
- 官方 `/act` 服务可用
- 真实 A2 样本可转 GO-1 payload

## 清理临时数据

```bash
find data/smoke_a2_samples -type f -delete
find data/smoke_a2_samples -depth -type d -empty -delete
find scripts -name __pycache__ -type d -exec find {} -type f -delete \;
find scripts -name __pycache__ -type d -empty -delete
```

## 参考

- AimDK 文档：`https://open.agibot.com/docs/aimdk`
- AimDK SDK：`2384363011954474097-AimDK-A2-Ultra-V1.3-0130.zip`
- AgiBot-World：`https://github.com/OpenDriveLab/AgiBot-World`
- GO-1 Air：`https://huggingface.co/agibot-world/GO-1-Air`
- GO-1 论文：`https://arxiv.org/abs/2503.06669`
