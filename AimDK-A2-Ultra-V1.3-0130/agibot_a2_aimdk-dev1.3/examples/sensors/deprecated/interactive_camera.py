import signal
import sys
import threading
import argparse
import time

import aimrt_py
from sensor_msgs.msg import Image

global_aimrt_core = None


class FrequencyStats:
    def __init__(self, logger):
        self.logger = logger
        self.message_count = 0
        self.interval_message_count = 0
        self.last_stats_time = time.time()
        self.start_time = time.time()
        self.latencies = []  # 存储这一秒内的延迟
        self.first_message = True

    def update(self, msg):
        current_time = time.time()
        self.message_count += 1
        self.interval_message_count += 1

        # 获取消息时间戳
        msg_timestamp = 0.0
        if hasattr(msg.header, "stamp") and msg.header.stamp:
            msg_timestamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9

        # 计算延迟（从消息时间戳到当前时间）
        if msg_timestamp > 0:
            latency_ms = (current_time - msg_timestamp) * 1000
            self.latencies.append(latency_ms)

        # 如果是第一条消息，显示详细信息（放在延迟计算之后）
        if self.first_message:
            self.first_message = False
            aimrt_py.info(
                self.logger,
                "=== Received /aima/hal/camera/interactive/color ===",
            )
            aimrt_py.info(self.logger, f"  header: {msg.header}")
            aimrt_py.info(self.logger, f"  width: {msg.width}")
            aimrt_py.info(self.logger, f"  height: {msg.height}")
            aimrt_py.info(self.logger, f"  encoding: {msg.encoding}")
            aimrt_py.info(self.logger, f"  is_bigendian: {msg.is_bigendian}")
            aimrt_py.info(self.logger, f"  step: {msg.step}")
            aimrt_py.info(self.logger, f"  data length: {len(msg.data)}")

        # 每秒输出一次统计
        if current_time - self.last_stats_time >= 1.0:
            time_elapsed = current_time - self.last_stats_time
            fps = (
                self.interval_message_count / time_elapsed if time_elapsed > 0 else 0.0
            )

            # 计算延迟统计
            if self.latencies:
                avg_latency = sum(self.latencies) / len(self.latencies)
                min_latency = min(self.latencies)
                max_latency = max(self.latencies)
            else:
                avg_latency = min_latency = max_latency = 0.0

            # 生成运行时间字符串
            total_runtime = current_time - self.start_time
            hours = int(total_runtime // 3600)
            minutes = int((total_runtime % 3600) // 60)
            seconds = int(total_runtime % 60)
            if hours > 0:
                interval_str = f"Runtime: {hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                interval_str = f"Runtime: {minutes:02d}:{seconds:02d}"

            log_message = (
                f"[1s] FPS: {fps:<4.1f} | "
                f"Latency(ms): Avg={avg_latency:<5.2f}, Min={min_latency:<5.2f}, Max={max_latency:<5.2f} | "
                f"{interval_str}"
            )

            aimrt_py.info(self.logger, log_message)

            # 重置计数器
            self.interval_message_count = 0
            self.latencies.clear()
            self.last_stats_time = current_time


def signal_handler(sig, frame):
    global global_aimrt_core

    if global_aimrt_core and (sig == signal.SIGINT or sig == signal.SIGTERM):
        global_aimrt_core.Shutdown()
        return

    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Example channel subscriber app.")
    parser.add_argument(
        "--cfg_file_path", type=str, default="", help="config file path"
    )
    args = parser.parse_args()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("AimRT start.")

    aimrt_core = aimrt_py.Core()

    global global_aimrt_core
    global_aimrt_core = aimrt_core

    # Initialize
    core_options = aimrt_py.CoreOptions()
    core_options.cfg_file_path = args.cfg_file_path
    aimrt_core.Initialize(core_options)

    # Create Module
    module_handle = aimrt_core.CreateModule("InteractiveCameraSubscriberModule")

    # Subscribe
    subscriber = module_handle.GetChannelHandle().GetSubscriber(
        "/aima/hal/camera/interactive/color"
    )
    assert subscriber, (
        "Get subscriber for topic '/aima/hal/camera/interactive/color' failed."
    )

    # 创建频率统计器
    freq_stats = FrequencyStats(module_handle.GetLogger())

    def EventHandle(msg: Image):
        # 更新频率统计
        freq_stats.update(msg)

    aimrt_py.Subscribe(subscriber, Image, EventHandle)

    # Start
    thread = threading.Thread(target=aimrt_core.Start)
    thread.start()

    while thread.is_alive():
        thread.join(1.0)

    print("AimRT exit.")


if __name__ == "__main__":
    main()
