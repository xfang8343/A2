#!/usr/bin/env python3
"""Record ROS2 Image topics to H.264 MP4 with a per-frame timestamp CSV.

Run only through a2_grasp_collect.py on the A2 ORIN. This subscriber never
publishes robot commands. MP4 has constant playback FPS; the CSV is the source
of truth when aligning video frames to rosbag messages.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
import time


def image_payload(msg) -> tuple[bytes, str]:
    """Return packed RGB/BGR bytes and the corresponding FFmpeg pixel format."""
    encoding = msg.encoding.lower()
    if encoding not in ("rgb8", "bgr8"):
        raise ValueError(f"不支持的图像编码 {msg.encoding!r}；需要 rgb8/bgr8")
    width, height, step = int(msg.width), int(msg.height), int(msg.step)
    if width <= 0 or height <= 0 or step < width * 3:
        raise ValueError(f"无效图像尺寸/步长: {width}x{height}, step={step}")
    raw = bytes(msg.data)
    if len(raw) < step * height:
        raise ValueError(f"图像数据长度不足: {len(raw)} < {step * height}")
    if step == width * 3:
        packed = raw[:height * step]
    else:
        packed = b"".join(raw[row * step:row * step + width * 3] for row in range(height))
    return packed, "rgb24" if encoding == "rgb8" else "bgr24"


class CameraWriter:
    def __init__(self, spec: dict, out: Path):
        self.name = spec["name"]
        self.topic = spec["topic"]
        self.fps = int(spec["fps"])
        self.out = out
        self.pending: queue.Queue = queue.Queue(maxsize=24)
        self.received = 0
        self.written = 0
        self.dropped = 0
        self.first_header_ns = None
        self.last_header_ns = None
        self.first_receive_ns = None
        self.last_receive_ns = None
        self.error = None
        self.encoder_exit_code = None
        self.shape = None
        self.encoder = None
        self.thread = threading.Thread(target=self.run, name=f"video-{self.name}")
        self.thread.start()

    def receive(self, msg):
        if self.error:
            return
        receive_ns = time.time_ns()
        header_ns = int(msg.header.stamp.sec) * 1_000_000_000 + int(msg.header.stamp.nanosec)
        self.received += 1
        try:
            self.pending.put_nowait((msg, header_ns, receive_ns))
        except queue.Full:
            self.dropped += 1

    def start_encoder(self, msg, pix_fmt: str):
        width, height = int(msg.width), int(msg.height)
        self.shape = (width, height, pix_fmt)
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "rawvideo", "-pixel_format", pix_fmt,
            "-video_size", f"{width}x{height}", "-framerate", str(self.fps),
            "-i", "pipe:0", "-an", "-c:v", "libx264",
            "-preset", "ultrafast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(self.out / f"{self.name}.mp4"),
        ]
        with (self.out / f"{self.name}_ffmpeg.log").open("wb") as log:
            self.encoder = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log,
            )

    def run(self):
        try:
            with (self.out / f"{self.name}_timestamps.csv").open(
                "w", newline="", encoding="utf-8"
            ) as handle:
                writer = csv.writer(handle)
                writer.writerow(("frame_index", "header_stamp_ns", "receive_unix_ns"))
                while True:
                    item = self.pending.get()
                    if item is None:
                        break
                    msg, header_ns, receive_ns = item
                    payload, pix_fmt = image_payload(msg)
                    shape = (int(msg.width), int(msg.height), pix_fmt)
                    if self.encoder is None:
                        self.start_encoder(msg, pix_fmt)
                    elif shape != self.shape:
                        raise RuntimeError(f"{self.name} 图像尺寸或编码中途改变: {self.shape} -> {shape}")
                    assert self.encoder.stdin is not None
                    self.encoder.stdin.write(payload)
                    writer.writerow((self.written, header_ns, receive_ns))
                    self.written += 1
                    if self.first_header_ns is None:
                        self.first_header_ns = header_ns
                        self.first_receive_ns = receive_ns
                    self.last_header_ns = header_ns
                    self.last_receive_ns = receive_ns
        except Exception as exc:
            self.error = str(exc)
        finally:
            if self.encoder is not None:
                try:
                    assert self.encoder.stdin is not None
                    self.encoder.stdin.close()
                    self.encoder_exit_code = self.encoder.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    self.encoder.kill()
                    self.encoder_exit_code = self.encoder.wait()
                    self.error = (self.error or "") + " ffmpeg 关闭超时"

    def finish(self):
        deadline = time.monotonic() + 5
        while self.thread.is_alive():
            try:
                self.pending.put(None, timeout=0.2)
                break
            except queue.Full:
                if time.monotonic() >= deadline:
                    if self.encoder is not None:
                        self.encoder.kill()
                    break
        self.thread.join(timeout=40)
        if self.thread.is_alive():
            if self.encoder is not None:
                self.encoder.kill()
            self.thread.join(timeout=5)
            self.error = (self.error or "") + " 编码线程未及时结束"
        return {
            "topic": self.topic, "fps_nominal": self.fps,
            "received": self.received, "written": self.written,
            "dropped": self.dropped, "encoder_exit_code": self.encoder_exit_code,
            "first_header_ns": self.first_header_ns,
            "last_header_ns": self.last_header_ns,
            "first_receive_ns": self.first_receive_ns,
            "last_receive_ns": self.last_receive_ns,
            "error": self.error,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)

    import rclpy
    from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
    from sensor_msgs.msg import Image

    stop = threading.Event()
    rclpy.init()
    node = rclpy.create_node("a2_grasp_video_recorder")
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    qos = QoSProfile(
        history=HistoryPolicy.KEEP_LAST, depth=10,
        reliability=ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.VOLATILE,
    )
    writers = [CameraWriter(spec, args.out) for spec in config["cameras"]]
    subscriptions = [
        node.create_subscription(Image, spec["topic"], writer.receive, qos)
        for spec, writer in zip(config["cameras"], writers)
    ]
    (args.out / "ready.json").write_text(json.dumps({"ready_unix_ns": time.time_ns(),
                                                      "topics": [w.topic for w in writers]}) + "\n")
    try:
        while not stop.is_set():
            rclpy.spin_once(node, timeout_sec=0.1)
            if any(w.error for w in writers):
                break
    finally:
        subscriptions.clear()
        node.destroy_node()
        rclpy.shutdown()
        cameras = {w.name: w.finish() for w in writers}
        errors = [f"{name}: {info['error']}" for name, info in cameras.items() if info["error"]]
        (args.out / "summary.json").write_text(
            json.dumps({"cameras": cameras, "errors": errors}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return 2 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
