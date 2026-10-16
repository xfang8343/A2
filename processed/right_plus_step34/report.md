# right+：第三、四步处理报告

处理成功 106 段，失败 0 段。
10 Hz 对齐行数：40097；新鲜度合格 40076，带陈旧数据标记 21。
源头部视频帧数 60117，含检查提示的示教 92 段。

## 观测与动作

状态为右臂 7 关节位置反馈＋右手 6 通道位置反馈；动作为相同顺序的目标位置命令，共 13 维。
按关节名称匹配，不按数组最后几项盲取；手臂单位 rad，手指保留 SDK 抽象位置单位。
原始命令 effort 作为辅助数组保留；夹持力是否固定及如何设置，需要在实际控制适配时核对。
实录右手 command effort 最小值 [13000.0, 8000.0, 8000.0, 8000.0, 8000.0, 8000.0]，最大值 [13000.0, 8000.0, 8000.0, 8000.0, 8000.0, 8000.0]；SDK 文档标称范围为 0～5700，若不一致，保持原始数据并在部署前核对固件和字段单位。
尚未拟合归一化器：划分训练集后仅用训练集计算，避免数据泄漏。

## 时间对齐

使用同一 ORIN 的接收时钟：关节使用 bag 接收时间，相机使用逐帧 CSV 的 receive_unix_ns。
每个决策时刻选择此前已收到的最新图像、两条反馈和两条命令；不使用未来帧、不做双向插值。
相机拍摄时间、各关节 header 时间均原样保留，用于后续延迟诊断；不把播放器秒数当成 ROS 时间。
仅在五路数据共同覆盖的区间上建立固定频率网格，不裁剪任务过程、不按动作阶段分段。
启动时未获得全部数据的边缘以及不足一个网格周期的尾部在 episode_quality.csv 中单独记录。
全数据中，视频开头缺少共同关节覆盖最长 1.047121 秒，尾部超出共同采样网格最长 0.172935 秒；原始视频完整保留。
valid_sample=False 的行仍保持在原时间位置，后续序列采样不能跨越它们，不能删行后压缩时间轴。

## 输出文件

- joint_schema.json：固定通道顺序、单位、动作与对齐规则。
- episodes/*.npz：对齐的 state、action、head_frame_index、整数纳秒时间戳及质量掩码。
- episodes/*.json：每段的原始范围、时间戳质量、数据来源指纹和提示。
- joint_ranges.csv：全数据观测/命令数值范围，属于数据统计，不是硬件安全限位。
- episode_quality.csv：每段样本数、源帧间隔和技术性边缘覆盖信息。
- preview.html：用浏览器离线打开，选择视频和关节，查看命令与反馈曲线；它不连接机器人。

原始视频不复制、不抽成图片。本阶段用精确帧索引关联视频，后续训练数据转换时再解码 RGB。
已检查 MP4 元信息帧数与 CSV 一致；尚未全量逐帧解码，也未把数据成功标注替换成自动任务评估。

## 数值范围

|通道|单位|反馈范围|命令范围|
|---|---|---|---|
|right_arm_joint1|rad|-1.2556 ～ 2.3795|-1.2668 ～ 2.3807|
|right_arm_joint2|rad|-1.5364 ～ -0.01545|-1.5359 ～ -0.0012486|
|right_arm_joint3|rad|-0.9638 ～ 2.8456|-0.96917 ～ 2.8465|
|right_arm_joint4|rad|0.10014 ～ 2.0075|0.1 ～ 2.094|
|right_arm_joint5|rad|-0.07763 ～ 2.6572|-0.079671 ～ 2.66|
|right_arm_joint6|rad|-0.23186 ～ 0.27751|-0.2 ～ 0.2|
|right_arm_joint7|rad|-0.2363 ～ 0.38644|-0.2 ～ 0.2|
|right_thumb_0|抽象位置|0 ～ 2015|1 ～ 1991|
|right_thumb_1|抽象位置|0 ～ 1574|1 ～ 1999|
|right_index|抽象位置|0 ～ 2004|1 ～ 1999|
|right_middle|抽象位置|0 ～ 1992|1 ～ 1999|
|right_ring|抽象位置|0 ～ 2003|1 ～ 1999|
|right_pinky|抽象位置|0 ～ 1999|1 ～ 1999|

## 逐段提示

- right_002/20261008_152628_bae9b3: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped; Video starts 0.597 s before all joint streams are available; source video retained, no invented joint observations
- right_003/20261008_152821_877267: Video starts 0.310 s before all joint streams are available; source video retained, no invented joint observations
- right_004/20261008_152941_14293b: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_005/20261008_153051_7076de: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_006/20261008_153204_f7a2fc: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped; Video starts 0.822 s before all joint streams are available; source video retained, no invented joint observations
- right_007/20261008_153318_36206b: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_008/20261008_153424_361f64: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped; Video starts 0.966 s before all joint streams are available; source video retained, no invented joint observations
- right_009/20261008_153530_deb275: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_010/20261008_153635_6978c9: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_011/20261009_141610_1c5983: 2 aligned rows have stale data; valid_sample mask must be used by future sequence sampler; Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_012/20261009_141803_2f1877: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_013/20261009_141942_4f0db4: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_014/20261009_142129_90c293: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_015/20261009_142328_c16109: Camera source frame gap 201.6 ms; all original frames retained; 1 aligned rows have stale data; valid_sample mask must be used by future sequence sampler; Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_016/20261009_144448_71de38: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_017/20261009_144633_aa4372: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_018/20261009_144825_b12307: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_019/20261009_145002_b5e57d: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_022/20261012_093521_9f0f48: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped; Video starts 0.826 s before all joint streams are available; source video retained, no invented joint observations
- right_023/20261012_093755_f543b8: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_025/20261012_094115_7ff8fd: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_027/20261012_101706_33f729: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_028/20261012_101847_b4ec81: Video starts 0.910 s before all joint streams are available; source video retained, no invented joint observations
- right_029/20261012_102304_8c53f6: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_030/20261012_102521_4ac259: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_031/20261012_103655_8bfc31: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_032/20261012_103833_90f7c6: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_033/20261012_104408_3a0b84: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_034/20261012_104642_631e1e: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_035/20261012_104944_9d004b: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped; Video starts 0.619 s before all joint streams are available; source video retained, no invented joint observations
- right_036/20261013_140213_2ebea7: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_037/20261013_140552_d26de4: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_038/20261013_140733_3b5efa: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_039/20261013_140922_5d7b21: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_040/20261013_141114_5de877: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_041/20261013_141257_41adfb: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_042/20261013_141433_67addd: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_044/20261013_141752_d99d1f: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_045/20261013_141931_37600f: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_047/20261013_144328_eab337: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_048/20261013_144457_40e5e3: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_050/20261013_144802_3b8d7f: 4 aligned rows have stale data; valid_sample mask must be used by future sequence sampler; Video starts 0.673 s before all joint streams are available; source video retained, no invented joint observations
- right_052/20261013_145054_5f9514: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_053/20261013_145221_0d19f0: Video starts 0.933 s before all joint streams are available; source video retained, no invented joint observations
- right_054/20261013_145353_d1ac97: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_055/20261013_145515_9fad33: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped; Video starts 0.619 s before all joint streams are available; source video retained, no invented joint observations
- right_057/20261013_151138_5e3928: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped; Video starts 0.427 s before all joint streams are available; source video retained, no invented joint observations
- right_058/20261013_151308_563973: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_059/20261013_151448_7e0dd3: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_060/20261013_151633_d107ae: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_061/20261013_151759_609ebf: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped; Video starts 0.502 s before all joint streams are available; source video retained, no invented joint observations
- right_062/20261013_151930_ee4ef1: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped; Video starts 0.718 s before all joint streams are available; source video retained, no invented joint observations
- right_063/20261013_152058_85712e: Camera source frame gap 268.9 ms; all original frames retained; 1 aligned rows have stale data; valid_sample mask must be used by future sequence sampler; Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_064/20261013_152223_5485f2: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped; Video starts 0.629 s before all joint streams are available; source video retained, no invented joint observations
- right_065/20261013_152347_18071e: Video starts 0.470 s before all joint streams are available; source video retained, no invented joint observations
- right_066/20261013_152514_a35cc1: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_067/20261013_152748_820628: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped; Video starts 0.905 s before all joint streams are available; source video retained, no invented joint observations
- right_068/20261013_152918_f7e48e: Camera source stamps repeat=1, backwards=0; original frame and receipt order retained; Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped; Video starts 1.023 s before all joint streams are available; source video retained, no invented joint observations
- right_069/20261014_101309_11203d: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_070/20261014_101521_609ac2: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_071/20261014_101640_7d6f20: 1 aligned rows have stale data; valid_sample mask must be used by future sequence sampler; Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped; Video starts 0.717 s before all joint streams are available; source video retained, no invented joint observations
- right_072/20261014_101803_d7a815: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_073/20261014_101924_cc0c80: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_075/20261014_102312_d9c9ca: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_076/20261014_102439_ff7068: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_077/20261014_102949_b56d5e: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped; Video starts 0.965 s before all joint streams are available; source video retained, no invented joint observations
- right_078/20261014_103113_71c8ed: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_079/20261014_103439_1ba287: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_149/20261015_153914_1cc798: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_151/20261015_154145_b02e6b: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_153/20261015_154310_5b12ff: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped; Video starts 0.885 s before all joint streams are available; source video retained, no invented joint observations
- right_155/20261015_154515_32fa90: 3 aligned rows have stale data; valid_sample mask must be used by future sequence sampler; Video starts 0.824 s before all joint streams are available; source video retained, no invented joint observations
- right_157/20261015_154702_004931: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_159/20261015_154816_2535cc: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_161/20261015_154928_b98bad: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_163/20261015_155328_8c6818: Camera source frame gap 201.5 ms; all original frames retained; 1 aligned rows have stale data; valid_sample mask must be used by future sequence sampler; Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_165/20261015_155455_3ad352: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_169/20261015_155811_11ba97: 1 aligned rows have stale data; valid_sample mask must be used by future sequence sampler; Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped; Video starts 0.767 s before all joint streams are available; source video retained, no invented joint observations
- right_171/20261015_155937_474155: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_173/20261015_160111_3c396c: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_175/20261015_160230_b6b8f9: Camera source frame gap 201.6 ms; all original frames retained; 1 aligned rows have stale data; valid_sample mask must be used by future sequence sampler; Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped; Video starts 1.047 s before all joint streams are available; source video retained, no invented joint observations
- right_177/20261015_161009_b41958: 3 aligned rows have stale data; valid_sample mask must be used by future sequence sampler; Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped; Video starts 0.663 s before all joint streams are available; source video retained, no invented joint observations
- right_179/20261015_161239_46271c: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped; Video starts 0.919 s before all joint streams are available; source video retained, no invented joint observations
- right_181/20261015_161409_8c4ace: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_183/20261015_161621_804cf7: Video starts 0.564 s before all joint streams are available; source video retained, no invented joint observations
- right_185/20261015_161742_2eb3d6: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_187/20261015_161900_f7c135: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped; Video starts 0.815 s before all joint streams are available; source video retained, no invented joint observations
- right_189/20261015_162018_7095b0: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped; Video starts 0.618 s before all joint streams are available; source video retained, no invented joint observations
- right_191/20261015_162137_deb3c9: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_193/20261015_162256_0c853b: 3 aligned rows have stale data; valid_sample mask must be used by future sequence sampler; Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped
- right_197/20261015_162551_186273: Video starts 0.614 s before all joint streams are available; source video retained, no invented joint observations
- right_199/20261015_162708_2ff123: Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped

官方字段依据：https://open.agibot.com/docs/aimdk/a2/v1_3/dev_guide/07-01-motion_control
