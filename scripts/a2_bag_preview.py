#!/usr/bin/env python3
"""Offline, read-only preview of the A2 SQLite grasp bag (stdlib only).

Exports camera PNGs and joint-position ranges without publishing ROS topics.
The parser supports the ROS 2 CDR forms of sensor_msgs/Image and JointState.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path
import sqlite3
import struct
import zlib


CAMERAS = {
    "head": "/aima/hal/rgbd_camera/head_front/color",
    "left": "/aima/hal/fish_eye_camera/chest_left/color",
    "right": "/aima/hal/fish_eye_camera/chest_right/color",
}
JOINTS = (
    "/motion/control/arm_joint_command",
    "/motion/control/arm_joint_state",
    "/motion/control/hand_joint_command",
    "/motion/control/hand_joint_state",
)


class Cdr:
    def __init__(self, data: bytes, base: int = 0):
        if len(data) < 4 or data[0] != 0 or data[1] not in (0, 1):
            raise ValueError("不是支持的 ROS 2 CDR 消息")
        self.data = data
        self.pos = 4
        self.base = base
        self.endian = "<" if data[1] == 1 else ">"

    def align(self, size: int) -> None:
        self.pos += -(self.pos - self.base) % size

    def fixed(self, fmt: str, size: int):
        self.align(size)
        value = struct.unpack_from(self.endian + fmt, self.data, self.pos)[0]
        self.pos += size
        return value

    def u8(self):
        return self.fixed("B", 1)

    def u32(self):
        return self.fixed("I", 4)

    def i32(self):
        return self.fixed("i", 4)

    def string(self):
        length = self.u32()
        if length < 1 or length > 100000 or self.pos + length > len(self.data):
            raise ValueError("CDR 字符串长度异常")
        raw = self.data[self.pos:self.pos + length]
        self.pos += length
        if raw[-1] != 0:
            raise ValueError("CDR 字符串缺少结束符")
        return raw[:-1].decode("utf-8")

    def header(self):
        sec = self.i32()
        nsec = self.u32()
        frame = self.string()
        return sec * 1_000_000_000 + nsec, frame

    def strings(self):
        count = self.u32()
        if count > 10000:
            raise ValueError("CDR 字符串数组过长")
        return [self.string() for _ in range(count)]

    def doubles(self):
        count = self.u32()
        if count > 10000:
            raise ValueError("CDR 数值数组过长")
        if count:
            self.align(8)
        size = 8 * count
        if self.pos + size > len(self.data):
            raise ValueError("CDR 数值数组不完整")
        values = struct.unpack_from(self.endian + str(count) + "d", self.data, self.pos)
        self.pos += size
        return values

    def bytes(self):
        count = self.u32()
        if self.pos + count > len(self.data):
            raise ValueError("CDR 图像数据不完整")
        value = self.data[self.pos:self.pos + count]
        self.pos += count
        return value


def decode_joint(data: bytes):
    last_error = None
    for base in (4, 0):
        try:
            r = Cdr(data, base)
            stamp, frame = r.header()
            names = r.strings()
            pos, vel, effort = r.doubles(), r.doubles(), r.doubles()
            if (len(pos) != len(names) or (vel and len(vel) != len(names))
                    or (effort and len(effort) != len(names)) or len(data) - r.pos > 3):
                raise ValueError("关节字段长度或 CDR 结尾不匹配")
            return {"stamp_ns": stamp, "frame": frame, "names": names,
                    "position": pos, "velocity": vel, "effort": effort}
        except (ValueError, struct.error, UnicodeDecodeError) as exc:
            last_error = exc
    raise ValueError(f"无法解码 JointState: {last_error}")


def decode_image(data: bytes):
    last_error = None
    for base in (4, 0):
        try:
            r = Cdr(data, base)
            stamp, frame = r.header()
            height, width = r.u32(), r.u32()
            encoding = r.string()
            bigendian, step = r.u8(), r.u32()
            pixels = r.bytes()
            if not (0 < height < 10000 and 0 < width < 10000 and
                    len(pixels) == height * step):
                raise ValueError("图像尺寸与数据长度不匹配")
            return {"stamp_ns": stamp, "frame": frame, "height": height,
                    "width": width, "encoding": encoding, "bigendian": bigendian,
                    "step": step, "pixels": pixels}
        except (ValueError, struct.error, UnicodeDecodeError) as exc:
            last_error = exc
    raise ValueError(f"无法解码 Image: {last_error}")


def png_chunk(kind: bytes, data: bytes) -> bytes:
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))


def save_png(image: dict, path: Path, stride: int) -> None:
    encoding = image["encoding"].lower()
    channels = {"rgb8": 3, "bgr8": 3, "rgba8": 4, "bgra8": 4, "mono8": 1}.get(encoding)
    if channels is None:
        raise ValueError(f"尚不支持图像编码 {image['encoding']}")
    width, height, step = image["width"], image["height"], image["step"]
    if step < width * channels:
        raise ValueError("图像行跨度小于像素宽度")
    out_width = len(range(0, width, stride))
    out_height = len(range(0, height, stride))
    raw = bytearray()
    pixels = image["pixels"]
    for y in range(0, height, stride):
        raw.append(0)  # PNG filter: none
        row = pixels[y * step:y * step + width * channels]
        for x in range(0, width, stride):
            px = row[x * channels:(x + 1) * channels]
            if channels == 1:
                raw.extend(px * 3)
            elif encoding.startswith("bgr"):
                raw.extend((px[2], px[1], px[0]))
            else:
                raw.extend(px[:3])
    header = struct.pack(">IIBBBBB", out_width, out_height, 8, 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", header)
                     + png_chunk(b"IDAT", zlib.compress(bytes(raw), 6))
                     + png_chunk(b"IEND", b""))


def db_files(session: Path):
    bag = session / "bag"
    files = sorted(bag.glob("*.db3"))
    if not files:
        raise RuntimeError("找不到完整的 .db3 文件；请等待 rsync 结束（.db3.* 是传输临时文件）")
    return files


def inspect(session: Path, output: Path, every: float, stride: int) -> None:
    manifest = json.loads((session / "manifest.json").read_text(encoding="utf-8"))
    files = db_files(session)
    if len(files) != 1:
        raise RuntimeError("当前预览工具仅支持单个 .db3 文件的采集")
    output.mkdir(parents=True, exist_ok=True)
    db_path = files[0]
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        topics = dict(conn.execute("SELECT name, id FROM topics"))
        start, end = conn.execute("SELECT MIN(timestamp), MAX(timestamp) FROM messages").fetchone()
        if start is None:
            raise RuntimeError("bag 中没有消息")
        duration = (end - start) / 1e9
        rows = []
        trace_rows = []
        for topic in JOINTS:
            if topic not in topics:
                continue
            ranges = {}
            count = 0
            last_bucket = -1
            query = "SELECT timestamp, data FROM messages WHERE topic_id=? ORDER BY timestamp"
            for timestamp, payload in conn.execute(query, (topics[topic],)):
                joint = decode_joint(payload)
                count += 1
                bucket = (timestamp - start) // 100_000_000  # 10 Hz preview
                if bucket != last_bucket:
                    trace_rows.extend(((timestamp-start)/1e9, joint["stamp_ns"], topic, name, value)
                                      for name, value in zip(joint["names"], joint["position"]))
                    last_bucket = bucket
                for name, value in zip(joint["names"], joint["position"]):
                    lo, hi = ranges.get(name, (value, value))
                    ranges[name] = (min(lo, value), max(hi, value))
            for name, (lo, hi) in sorted(ranges.items()):
                rows.append((topic, count, name, lo, hi, hi - lo))
        with (output / "joint_ranges.csv").open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(("topic", "messages", "joint_name", "min_position", "max_position", "range"))
            writer.writerows(rows)
        with (output / "joint_trace_10hz.csv").open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(("bag_time_s", "header_time_ns", "topic", "joint_name", "position"))
            writer.writerows(trace_rows)
        samples = []
        offsets = [min(1.0 + i * every, duration - 0.1)
                   for i in range(max(1, int((duration - 1) // every) + 1))]
        for offset in offsets:
            cells = []
            target = start + int(offset * 1e9)
            for label, topic in CAMERAS.items():
                if topic not in topics:
                    cells.append((label, None, "话题缺失"))
                    continue
                found = conn.execute(
                    "SELECT timestamp, data FROM messages WHERE topic_id=? "
                    "ORDER BY ABS(timestamp-?) LIMIT 1", (topics[topic], target)
                ).fetchone()
                if found is None:
                    cells.append((label, None, "无图像"))
                    continue
                stamp, payload = found
                image = decode_image(payload)
                name = f"{offset:06.1f}s_{label}.png"
                save_png(image, output / name, stride)
                cells.append((label, name, f"{image['width']}x{image['height']} "
                             f"{image['encoding']}；包内时间 {(stamp-start)/1e9:.2f}s"))
            samples.append((offset, cells))
    parts = ["<!doctype html><meta charset='utf-8'><title>A2 抓取预览</title>",
             "<style>body{font:16px sans-serif;max-width:1400px;margin:auto}"
             "table{border-collapse:collapse}td,th{border:1px solid #aaa;padding:8px}"
             "img{width:100%;max-width:400px}</style>",
             f"<h1>A2 抓取预览</h1><p>任务：{html.escape(str(manifest.get('task')))}；"
             f"物体：{html.escape(str(manifest.get('object')))}；"
             f"结果：{html.escape(str(manifest.get('outcome')))}；"
             f"时长：{duration:.2f}s</p>",
             "<p>关节范围见 <a href='joint_ranges.csv'>joint_ranges.csv</a>；"
             "约 10 Hz 的时间序列见 <a href='joint_trace_10hz.csv'>joint_trace_10hz.csv</a>。"
             "这些数值不能单独证明抓取成功。</p>",
             "<table><tr><th>时间</th><th>头部</th><th>左胸</th><th>右胸</th></tr>"]
    for offset, cells in samples:
        parts.append(f"<tr><th>{offset:.1f}s</th>")
        for label, name, detail in cells:
            parts.append("<td>" + (f"<img src='{html.escape(name)}'><br>" if name else "")
                         + html.escape(detail) + "</td>")
        parts.append("</tr>")
    parts.append("</table>")
    (output / "index.html").write_text("\n".join(parts), encoding="utf-8")
    print(f"预览完成：{output / 'index.html'}")
    print(f"关节范围：{output / 'joint_ranges.csv'}")
    print(f"关节轨迹：{output / 'joint_trace_10hz.csv'}")
    print(f"包时长：{duration:.2f}s；相机采样点：{len(samples)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path, help="包含 manifest.json 和 bag/ 的采集目录")
    parser.add_argument("--out", type=Path, help="预览输出目录；默认采集目录下的 preview/")
    parser.add_argument("--every", type=float, default=5.0, help="每隔多少秒抽一组相机图，默认 5")
    parser.add_argument("--stride", type=int, default=2, help="图像隔点采样倍率，默认 2")
    args = parser.parse_args()
    if args.every <= 0 or args.stride <= 0:
        parser.error("--every 和 --stride 必须大于 0")
    try:
        inspect(args.session, args.out or args.session / "preview", args.every, args.stride)
    except (OSError, sqlite3.Error, ValueError, RuntimeError, KeyError) as exc:
        parser.exit(2, f"错误：{exc}\n")


if __name__ == "__main__":
    main()
