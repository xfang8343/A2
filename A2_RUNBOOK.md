# A2 联调 Runbook

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
