#!/usr/bin/env python3
"""Read-only A2 v1.3 upper-body grasp recording with rosbag2.

Run on the robot ORIN after sourcing ROS 2 Humble and the AimDK ROS message
environment. This program never publishes commands or changes robot state.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
import uuid


ARM = "/motion/control/arm_joint_state"
HAND = "/motion/control/hand_joint_state"
HEAD = "/aima/hal/rgbd_camera/head_front/color"
LEFT = "/aima/hal/fish_eye_camera/chest_left/color"
RIGHT = "/aima/hal/fish_eye_camera/chest_right/color"
DEPTH = "/aima/hal/rgbd_camera/head_front/depth"
STATES = (ARM, HAND)
CAMERA_TOPICS = (HEAD, LEFT, RIGHT)
VIDEO_NAMES = {HEAD: "head", LEFT: "chest_left", RIGHT: "chest_right"}
VIDEO_FPS = {HEAD: 15, LEFT: 30, RIGHT: 30}
CORE = STATES + CAMERA_TOPICS
CONTROL = (
    "/motion/control/arm_joint_command",
    "/motion/control/hand_joint_command",
    "/rc/command",
    "/rc/virtual/joint_states",
    "/rc/virtual/joint_states_change",
    "/rc/virtual/joint_descarts_change",
)
DOCS = (
    "https://open.agibot.com/docs/aimdk/a2/v1_3/dev_guide/03-second_develop_interface_overview",
    "https://open.agibot.com/docs/aimdk/a2/v1_3/dev_guide/07-01-motion_control",
    "https://open.agibot.com/docs/aimdk/a2/v1_3/dev_guide/07-04-sensor_data",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def save_json(path: Path, data: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def discover_topics() -> dict[str, str]:
    if not shutil.which("ros2"):
        raise RuntimeError("未找到 ros2；请在 ORIN 上 source /opt/ros/humble/setup.bash")
    result = subprocess.run(
        ["ros2", "topic", "list", "-t"], capture_output=True, text=True, timeout=20
    )
    if result.returncode:
        raise RuntimeError(f"ros2 topic list 失败: {result.stderr.strip()}")
    topics = {}
    for line in result.stdout.splitlines():
        match = re.fullmatch(r"\s*(/\S+)\s+\[([^\]]+)\]\s*", line)
        if match:
            topics[match.group(1)] = match.group(2)
    if not topics:
        raise RuntimeError("ROS2 未发现任何 topic；请检查 DDS 环境和机器人连接")
    return topics


def control_topics(discovered: dict[str, str]) -> list[str]:
    # AimDK devices can expose additional protobuf wrapper topics under /rc/data/.
    return sorted(
        topic for topic in discovered
        if topic in CONTROL or topic.startswith("/rc/data/pb_")
    )


def camera_topics(args: argparse.Namespace) -> list[str]:
    """Select RGB camera topics; --side is a task label, not a joint filter."""
    side_cameras = {
        "left": [LEFT], "right": [RIGHT], "both": [LEFT, RIGHT], "none": [],
    }[args.side]
    cameras = {
        "all": [HEAD, LEFT, RIGHT],
        "head-side": [HEAD] + side_cameras,
        "head": [HEAD],
        "side": side_cameras,
        "none": [],
    }[args.cameras]
    return cameras


def video_topics(args: argparse.Namespace) -> list[str]:
    return camera_topics(args) if args.visual_mode in ("video", "both") else []


def required_topics(args: argparse.Namespace) -> list[str]:
    """Select bag topics; A2 arm/hand JointState topics contain both sides."""
    if args.depth and (args.cameras == "none" or args.visual_mode not in ("images", "both")):
        raise ValueError("--depth 仅能与 --visual-mode images/both 及非 none 相机组合使用")
    required = list(STATES)
    if args.visual_mode in ("images", "both"):
        required.extend(camera_topics(args))
        if args.depth:
            required.append(DEPTH)
    required.extend(args.extra_topic)
    return list(dict.fromkeys(required))


def selection(args: argparse.Namespace, discovered: dict[str, str]) -> tuple[list[str], list[str]]:
    required = required_topics(args)
    missing = sorted((set(required) | set(video_topics(args))) - discovered.keys())
    commands = control_topics(discovered)
    if args.skip_proto:
        commands = [topic for topic in commands if not topic.startswith("/rc/data/pb_")]
    if missing:
        raise RuntimeError("缺少必需 topic: " + ", ".join(missing))
    if not args.allow_state_only:
        missing_commands = [topic for topic in CONTROL[:2] if topic not in commands]
        if missing_commands:
            raise RuntimeError(
                "缺少上肢命令 topic: " + ", ".join(missing_commands)
                + "；请先启动官方遥操或指定 --allow-state-only 做只读试录"
            )
    topics = list(dict.fromkeys(required + commands))
    return topics, commands


def preflight(args: argparse.Namespace) -> tuple[dict[str, str], list[str], list[str]]:
    discovered = discover_topics()
    selected, commands = selection(args, discovered)
    for topic in video_topics(args):
        if discovered[topic] != "sensor_msgs/msg/Image":
            raise RuntimeError(f"视频源不是 sensor_msgs/msg/Image: {topic} [{discovered[topic]}]")
    if video_topics(args):
        helper = Path(__file__).with_name("a2_video_recorder.py")
        if not helper.is_file():
            raise RuntimeError(f"缺少视频录制脚本: {helper}；请同时复制到机器人")
        if not shutil.which("ffmpeg"):
            raise RuntimeError("视频模式需要 ORIN 上可用的 ffmpeg")
        encoder = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"],
                                 capture_output=True, text=True, timeout=15)
        if encoder.returncode or not re.search(r"\blibx264\b", encoder.stdout):
            raise RuntimeError("ffmpeg 缺少 libx264 编码器，无法写入 H.264 MP4")
        ros_import = subprocess.run([sys.executable, "-c", "import rclpy; import sensor_msgs.msg"],
                                    capture_output=True, text=True, timeout=10)
        if ros_import.returncode:
            raise RuntimeError("视频模式缺少 ROS2 Python 依赖 rclpy/sensor_msgs: "
                               + ros_import.stderr.strip())
    if args.skip_proto:
        print("提示：已跳过 /rc/data/pb_*；仅录制标准上肢命令和状态。")
    else:
        for kind in sorted({discovered[topic] for topic in selected
                            if discovered[topic].startswith("ros2_plugin_proto/")}):
            check = subprocess.run(["ros2", "interface", "show", kind],
                                   capture_output=True, text=True, timeout=10)
            if check.returncode:
                raise RuntimeError(
                    f"缺少消息类型 {kind}；请 source AimDK aarch64 包中的 "
                    "ros2_plugin_proto/local_setup.bash，或加 --skip-proto 只录标准话题"
                )
    if os.environ.get("ROS_DOMAIN_ID") != "232":
        print("提示：官方 v1.3 的 ROS_DOMAIN_ID 为 232；当前值为 "
              + repr(os.environ.get("ROS_DOMAIN_ID")), file=sys.stderr)
    print(f"任务侧: {args.side}；相机组合: {args.cameras}；视觉格式: {args.visual_mode}")
    print("将写入 rosbag：")
    for topic in selected:
        print(f"  {topic} [{discovered[topic]}]")
    if video_topics(args):
        print("将编码为 MP4（同时保存逐帧时间戳）：")
        for topic in video_topics(args):
            print(f"  {VIDEO_NAMES[topic]} <- {topic} [{discovered[topic]}]")
    if not commands:
        print("提示：当前仅能采集观测；不能形成有命令标签的示教样本。")
    return discovered, selected, commands


def write_qos(path: Path, topics: list[str]) -> None:
    # A2 v1.3 documents BEST_EFFORT, KEEP_LAST 10 for machine topics.
    lines = []
    for topic in topics:
        lines.extend((f"{topic}:", "  history: keep_last", "  depth: 10",
                      "  reliability: best_effort", "  durability: volatile"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def bag_counts(bag: Path) -> dict[str, dict]:
    result: dict[str, dict] = {}
    db_files = sorted(bag.glob("*.db3"))
    if not db_files:
        raise RuntimeError(f"没有找到 rosbag2 SQLite 数据文件: {bag}")
    for db_file in db_files:
        uri = f"file:{db_file}?mode=ro"
        with sqlite3.connect(uri, uri=True) as conn:
            rows = conn.execute(
                "SELECT t.name, t.type, COUNT(m.id), MIN(m.timestamp), MAX(m.timestamp) "
                "FROM topics t LEFT JOIN messages m ON m.topic_id=t.id "
                "GROUP BY t.id"
            )
            for name, kind, count, first, last in rows:
                item = result.setdefault(name, {"type": kind, "messages": 0,
                                                "first_bag_ns": None, "last_bag_ns": None})
                item["messages"] += count
                if first is not None:
                    item["first_bag_ns"] = min(
                        first, item["first_bag_ns"] if item["first_bag_ns"] is not None else first
                    )
                    item["last_bag_ns"] = max(
                        last, item["last_bag_ns"] if item["last_bag_ns"] is not None else last
                    )
    for item in result.values():
        first, last = item["first_bag_ns"], item["last_bag_ns"]
        item["approx_hz"] = round((item["messages"] - 1) * 1e9 / (last - first), 2) \
            if item["messages"] > 1 and last > first else None
    return result


def validate_session(folder: Path, save: bool = True) -> dict:
    manifest_path = folder / "manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"没有找到 manifest.json: {folder}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    counts = bag_counts(folder / "bag")
    required = manifest["required_topics"]
    missing = [topic for topic in required if counts.get(topic, {}).get("messages", 0) == 0]
    command_count = sum(counts.get(topic, {}).get("messages", 0)
                        for topic in manifest["control_topics"])
    errors = [f"无消息: {topic}" for topic in missing]
    exit_code = manifest.get("recorder_exit_code")
    if exit_code is not None and exit_code not in (0, -signal.SIGINT):
        errors.append(f"录包进程异常退出: {exit_code}")
    elapsed = manifest.get("elapsed_s", 0)
    if elapsed >= 10:
        for topic in required:
            if topic not in (*CORE, DEPTH):
                continue
            n = counts.get(topic, {}).get("messages", 0)
            if n and n / elapsed < 1:
                errors.append(f"采样率过低: {topic} ({n / elapsed:.2f} Hz，按整段时长计算)")
    if not manifest["allow_state_only"]:
        for topic in CONTROL[:2]:
            if counts.get(topic, {}).get("messages", 0) == 0:
                errors.append(f"无上肢命令消息: {topic}，不能作为动作示教样本")
    videos = {}
    expected_videos = manifest.get("video_topics", [])
    video_exit = manifest.get("video_recorder_exit_code")
    if video_exit is not None and video_exit not in (0, -signal.SIGINT):
        errors.append(f"视频录制进程异常退出: {video_exit}")
    if expected_videos:
        summary_path = folder / "video" / "summary.json"
        if not summary_path.is_file():
            errors.append("缺少 video/summary.json；视频录制未正常结束")
        else:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            videos = summary.get("cameras", {})
            for topic in expected_videos:
                name = VIDEO_NAMES[topic]
                info = videos.get(name, {})
                movie = folder / "video" / f"{name}.mp4"
                stamps = folder / "video" / f"{name}_timestamps.csv"
                if not movie.is_file() or movie.stat().st_size == 0 or not stamps.is_file():
                    errors.append(f"缺少有效视频或时间戳: {name}")
                else:
                    with stamps.open(newline="", encoding="utf-8") as handle:
                        rows = list(csv.DictReader(handle))
                    if len(rows) != info.get("written", 0):
                        errors.append(f"视频帧数与时间戳行数不一致: {name}")
                    elif any(int(row["frame_index"]) != index for index, row in enumerate(rows)):
                        errors.append(f"视频帧序号不连续: {name}")
                if info.get("written", 0) == 0:
                    errors.append(f"无视频帧: {name}")
                elif elapsed >= 10 and info["written"] / elapsed < VIDEO_FPS[topic] * 0.5:
                    errors.append(
                        f"视频采样率过低: {name} ({info['written'] / elapsed:.2f} Hz；"
                        f"标称 {VIDEO_FPS[topic]} Hz)"
                    )
                if info.get("encoder_exit_code") != 0:
                    errors.append(f"视频编码失败: {name} (exit={info.get('encoder_exit_code')})")
                received = info.get("received", 0)
                if received and info.get("dropped", 0) / received > 0.1:
                    errors.append(f"视频丢帧超过 10%: {name}")
            if summary.get("errors"):
                errors.extend(f"视频录制错误: {item}" for item in summary["errors"])
    result = {"checked_utc": utc_now(), "valid": not errors, "errors": errors,
              "control_messages": command_count, "topics": counts, "videos": videos}
    if save:
        manifest["validation"] = result
        save_json(manifest_path, manifest)
    return result


def stop_recorder(proc: subprocess.Popen, timeout_s: int = 30) -> int:
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGINT)
        except ProcessLookupError:
            pass
    try:
        return proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            return proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            return proc.wait()


def stop_video_recorder(proc: subprocess.Popen, already_signalled: bool = False) -> int:
    # FFmpeg children share this process group. Signal only the ROS subscriber so it
    # can drain frames and close FFmpeg stdin; signalling the whole group corrupts MP4.
    if not already_signalled and proc.poll() is None:
        proc.send_signal(signal.SIGINT)
    try:
        return proc.wait(timeout=90)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            return proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            return proc.wait()


def record(args: argparse.Namespace) -> int:
    discovered, selected, commands = preflight(args)
    base = Path(args.out).expanduser().resolve()
    base.mkdir(parents=True, exist_ok=True)
    folder = base / (datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6])
    folder.mkdir()
    required = required_topics(args)
    manifest = {
        "format": "a2_grasp_rosbag_v1", "created_utc": utc_now(),
        "task": args.task, "object": args.object, "operator": args.operator,
        "side": args.side, "camera_set": args.cameras,
        "visual_mode": args.visual_mode, "video_topics": video_topics(args),
        "video_fps": {VIDEO_NAMES[t]: VIDEO_FPS[t] for t in video_topics(args)},
        "outcome": "unlabelled", "notes": "", "robot_model": "A2",
        "aimdk_version": "v1.3", "ros_domain_id": os.environ.get("ROS_DOMAIN_ID"),
        "required_topics": list(dict.fromkeys(required)),
        "control_topics": commands, "selected_topics": selected,
        "discovered_types": {topic: discovered[topic]
                             for topic in dict.fromkeys(selected + video_topics(args))},
        "allow_state_only": args.allow_state_only, "skip_proto": args.skip_proto,
        "requested_duration_s": args.duration, "docs": DOCS,
    }
    save_json(folder / "manifest.json", manifest)
    write_qos(folder / "qos.yaml", selected)
    cmd = ["ros2", "bag", "record", "-s", "sqlite3", "-o", str(folder / "bag"),
           "--qos-profile-overrides-path", str(folder / "qos.yaml"), *selected]
    print(f"\n采集目录: {folder}\n录制命令: {' '.join(cmd)}\n按 Ctrl+C 提前结束。", flush=True)
    video_proc = None
    video_log = None
    video_config = None
    if video_topics(args):
        video_dir = folder / "video"
        video_dir.mkdir()
        video_config = video_dir / "config.json"
        save_json(video_config, {"cameras": [
            {"name": VIDEO_NAMES[t], "topic": t, "fps": VIDEO_FPS[t]}
            for t in video_topics(args)
        ]})
        helper_cmd = [sys.executable, str(Path(__file__).with_name("a2_video_recorder.py")),
                      "--config", str(video_config), "--out", str(video_dir)]
        video_log = (folder / "video_recorder.log").open("w", encoding="utf-8")
        try:
            video_proc = subprocess.Popen(helper_cmd, stdout=video_log,
                                          stderr=subprocess.STDOUT, start_new_session=True)
            ready = video_dir / "ready.json"
            deadline = time.monotonic() + 15
            while not ready.exists():
                if video_proc.poll() is not None:
                    raise RuntimeError("视频录制进程启动失败；查看 video_recorder.log")
                if time.monotonic() >= deadline:
                    raise RuntimeError("视频录制进程未就绪；查看 video_recorder.log")
                time.sleep(0.1)
        except BaseException as exc:
            if video_proc is not None:
                stop_video_recorder(video_proc)
            video_log.close()
            manifest["record_error"] = str(exc)
            save_json(folder / "manifest.json", manifest)
            raise
    started = time.monotonic()
    code = None
    video_code = None
    stopped = started
    with (folder / "recorder.log").open("w", encoding="utf-8") as log:
        try:
            proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT,
                                    start_new_session=True)
        except OSError as exc:
            if video_proc is not None:
                video_code = stop_video_recorder(video_proc)
                video_log.close()
            manifest["record_error"] = str(exc)
            save_json(folder / "manifest.json", manifest)
            raise RuntimeError(f"无法启动 ros2 bag record: {exc}") from exc
        try:
            while proc.poll() is None:
                if video_proc is not None and video_proc.poll() is not None:
                    print("视频进程提前结束，正在停止 rosbag；查看 video_recorder.log",
                          file=sys.stderr, flush=True)
                    break
                if args.duration and time.monotonic() - started >= args.duration:
                    break
                time.sleep(0.2)
        except KeyboardInterrupt:
            print("\n正在结束录制并写入索引…", flush=True)
        finally:
            stopped = time.monotonic()
            video_signalled = False
            if video_proc is not None and video_proc.poll() is None:
                video_proc.send_signal(signal.SIGINT)
                video_signalled = True
            code = stop_recorder(proc)
            if video_proc is not None:
                video_code = stop_video_recorder(video_proc, already_signalled=video_signalled)
                video_log.close()
    manifest["ended_utc"] = utc_now()
    manifest["elapsed_s"] = round(stopped - started, 2)
    manifest["recorder_exit_code"] = code
    if video_proc is not None:
        manifest["video_recorder_exit_code"] = video_code
    save_json(folder / "manifest.json", manifest)
    try:
        result = validate_session(folder)
    except (RuntimeError, sqlite3.Error) as exc:
        print(f"采集未通过校验: {exc}；查看 {folder / 'recorder.log'}", file=sys.stderr)
        return 2
    for topic, item in result["topics"].items():
        print(f"{item['messages']:>7}  {topic}  {item['approx_hz']} Hz")
    for name, item in result["videos"].items():
        print(f"{item.get('written', 0):>7}  video/{name}.mp4"
              f"  dropped={item.get('dropped', 0)}")
    if not result["valid"]:
        print("采集未通过校验: " + "; ".join(result["errors"])
              + f"；查看 {folder / 'recorder.log'}", file=sys.stderr)
        return 2
    print(f"采集完成。请标注结果：python {Path(__file__).name} label {folder} --outcome success")
    return 0


def label(args: argparse.Namespace) -> int:
    path = Path(args.session) / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["outcome"] = args.outcome
    if args.notes is not None:
        manifest["notes"] = args.notes
    manifest["labelled_utc"] = utc_now()
    save_json(path, manifest)
    print(f"已标注: {path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("preflight", "record"):
        p = sub.add_parser(name)
        p.add_argument("--depth", action="store_true", help="同时采集头部深度图")
        p.add_argument("--side", choices=("left", "right", "both", "none"), default="both",
                       help="本次任务侧；none 表示不指定侧别；关节原始 topic 仍包含双侧")
        p.add_argument("--cameras", choices=("all", "head-side", "head", "side", "none"),
                       default="all", help="录制的相机组合；none 表示不录制任何相机，默认 all")
        p.add_argument("--visual-mode", choices=("images", "video", "both", "none"),
                       default="images", help="images=相机原始 Image 入 bag（原行为）；"
                       "video=只保存 MP4；both=两者；none=无视觉数据")
        p.add_argument("--skip-proto", action="store_true",
                       help="缺少 ros2_plugin_proto 时跳过 /rc/data/pb_* 话题")
        p.add_argument("--extra-topic", action="append", default=[], metavar="TOPIC")
        p.add_argument("--allow-state-only", action="store_true",
                       help="允许缺少上肢命令；仅供试录或观测数据使用")
        if name == "record":
            p.add_argument("--task", required=True, help="动作描述，如 grasp_cup")
            p.add_argument("--object", required=True, help="抓取物体标识")
            p.add_argument("--operator", required=True, help="操作员标识")
            p.add_argument("--duration", type=float, default=60,
                           help="秒；0 表示直到 Ctrl+C")
            p.add_argument("--out", default="data/grasp", help="采集根目录")
    v = sub.add_parser("validate")
    v.add_argument("session", help="包含 manifest.json 与 bag/ 的单次采集目录")
    l = sub.add_parser("label")
    l.add_argument("session")
    l.add_argument("--outcome", choices=("success", "failure", "uncertain"), required=True)
    l.add_argument("--notes")
    args = parser.parse_args()
    try:
        if args.command == "preflight":
            preflight(args)
            return 0
        if args.command == "record":
            if args.duration < 0:
                parser.error("--duration 不能为负数")
            return record(args)
        if args.command == "label":
            return label(args)
        result = validate_session(Path(args.session))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["valid"] else 2
    except (RuntimeError, OSError, sqlite3.Error, KeyError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
