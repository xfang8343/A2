#!/usr/bin/env python3
"""Audit A2 right-side JointState recordings and align them with head video.

This is offline preprocessing, not a trainer or a robot controller. Inputs are
read only. Images stay in the original MP4; frame indices locate observations.
Requires numpy and opencv-python, but no ROS installation or GPU.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import struct
import sys

import cv2
import numpy as np

from a2_bag_preview import Cdr


TOPICS = {
    "arm_state": "/motion/control/arm_joint_state",
    "hand_state": "/motion/control/hand_joint_state",
    "arm_command": "/motion/control/arm_joint_command",
    "hand_command": "/motion/control/hand_joint_command",
}
ARM_NAMES = [f"right_arm_joint{i}" for i in range(1, 8)]
HAND_NAMES = ["right_thumb_0", "right_thumb_1", "right_index",
              "right_middle", "right_ring", "right_pinky"]
CHANNELS = ARM_NAMES + HAND_NAMES
HAND_ALIASES = {
    "R_thumb_swing_joint": "right_thumb_0", "R_thumb_1_joint": "right_thumb_1",
    "R_index_1_joint": "right_index", "R_middle_1_joint": "right_middle",
    "R_ring_1_joint": "right_ring", "R_little_1_joint": "right_pinky",
}
DOC_URL = "https://open.agibot.com/docs/aimdk/a2/v1_3/dev_guide/07-01-motion_control"


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
                    + "\n", encoding="utf-8")


def canonical_name(name):
    return HAND_ALIASES.get(name, re.sub(r"^idx\d+_", "", name))


def right_indices(names, group):
    expected = ARM_NAMES if group == "arm" else HAND_NAMES
    normalized = [canonical_name(name) for name in names]
    for name in expected:
        if normalized.count(name) != 1:
            raise ValueError(f"Expected exactly one {name}, got names={names}")
    return [normalized.index(name) for name in expected]


def parse_joint(payload, base=None):
    """Accept both recorded CDR alignment forms; retain the chosen one per topic."""
    errors = []
    for offset in ((4, 0) if base is None else (base,)):
        try:
            reader = Cdr(payload, offset)
            header_ns, _ = reader.header()
            names = reader.strings()
            positions = reader.doubles()
            velocity = reader.doubles()
            effort = reader.doubles()
            if len(names) != len(positions) or not names:
                raise ValueError("JointState name/position lengths disagree")
            if not 0 <= len(payload) - reader.pos <= 3:
                raise ValueError("Unexpected CDR trailing bytes")
            return offset, header_ns, tuple(names), positions, velocity, effort
        except (ValueError, UnicodeError, IndexError, struct.error) as exc:
            errors.append(str(exc))
    raise ValueError("Cannot parse JointState: " + "; ".join(errors))


def stats(values):
    values = np.asarray(values, dtype=np.float64)
    if not len(values):
        return None
    return {"min": float(np.min(values)), "median": float(np.median(values)),
            "p95": float(np.percentile(values, 95)),
            "p99": float(np.percentile(values, 99)), "max": float(np.max(values))}


def latest_indices(arrival_ns, grid_ns):
    """Zero-order hold: never consume a message received after a decision."""
    indices = np.searchsorted(arrival_ns, grid_ns, side="right") - 1
    if np.any(indices < 0):
        raise ValueError("Decision occurs before first available observation")
    return indices


def read_joint_streams(session):
    streams = {key: {"arrival": [], "header": [], "position": [], "effort": [],
                     "source_names": set(), "aux_lengths": Counter()}
               for key in TOPICS}
    bases, name_cache = {}, {}
    files = sorted((session / "bag").glob("*.db3"))
    if not files:
        raise ValueError("No SQLite rosbag found")
    for db in files:
        with sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True) as conn:
            topic_rows = conn.execute("SELECT id,name,type FROM topics").fetchall()
            ids = {}
            for tid, name, kind in topic_rows:
                for key, wanted in TOPICS.items():
                    if name == wanted:
                        if kind != "sensor_msgs/msg/JointState":
                            raise ValueError(f"Unexpected type {name}: {kind}")
                        ids[tid] = key
            if not ids:
                continue
            marks = ",".join("?" for _ in ids)
            query = ("SELECT topic_id,timestamp,data FROM messages WHERE topic_id IN ("
                     + marks + ") ORDER BY timestamp,id")
            for tid, receive_ns, payload in conn.execute(query, tuple(ids)):
                key = ids[tid]
                base, header_ns, names, position, velocity, effort = parse_joint(
                    payload, bases.get(key))
                bases[key] = base
                cache_key = (key, names)
                if cache_key not in name_cache:
                    indices = right_indices(names, key.split("_")[0])
                    name_cache[cache_key] = indices
                    streams[key]["source_names"].add(tuple(names[i] for i in indices))
                indices = name_cache[cache_key]
                stream = streams[key]
                stream["arrival"].append(receive_ns)
                stream["header"].append(header_ns)
                stream["position"].append(tuple(position[i] for i in indices))
                stream["effort"].append(tuple(effort[i] for i in indices)
                                        if len(effort) == len(names) else ())
                stream["aux_lengths"][(len(names), len(velocity), len(effort))] += 1
    for key, stream in streams.items():
        if not stream["arrival"]:
            raise ValueError(f"No messages: {TOPICS[key]}")
        stream["arrival"] = np.asarray(stream["arrival"], dtype=np.int64)
        stream["header"] = np.asarray(stream["header"], dtype=np.int64)
        stream["position"] = np.asarray(stream["position"], dtype=np.float64)
        # Splits are read independently; stable receipt order defines the final sequence.
        order = np.argsort(stream["arrival"], kind="stable")
        for field in ("arrival", "header", "position"):
            stream[field] = stream[field][order]
        if not np.isfinite(stream["position"]).all():
            raise ValueError(f"Non-finite right joint position: {key}")
        lengths = {len(row) for row in stream["effort"]}
        if lengths == {stream["position"].shape[1]}:
            stream["effort"] = np.asarray(stream["effort"], dtype=np.float64)[order]
        else:
            stream["effort"] = None
    return streams


def read_camera(session):
    with (session / "video/head_timestamps.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if len(rows) < 2:
        raise ValueError("Too few head video timestamps")
    camera = {
        "frame": np.asarray([int(r["frame_index"]) for r in rows], dtype=np.int64),
        "header": np.asarray([int(r["header_stamp_ns"]) for r in rows], dtype=np.int64),
        "arrival": np.asarray([int(r["receive_unix_ns"]) for r in rows], dtype=np.int64),
    }
    if not np.array_equal(camera["frame"], np.arange(len(rows))):
        raise ValueError("Video frame indices are not consecutive from zero")
    if np.any(np.diff(camera["arrival"]) < 0):
        raise ValueError("Head receive timestamps move backwards")
    if np.any(camera["header"] <= 0):
        raise ValueError("Invalid camera source timestamps")
    # Repeated capture stamps do not destroy distinct recorded frames. Receipt
    # time plus frame_index remains causal and ordered; report source anomalies.
    capture = cv2.VideoCapture(str(session / "video/head.mp4"))
    try:
        if not capture.isOpened():
            raise ValueError("Cannot open head MP4")
        camera["width"] = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        camera["height"] = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        camera["fps"] = float(capture.get(cv2.CAP_PROP_FPS))
        camera["mp4_frame_count"] = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        capture.release()
    if camera["mp4_frame_count"] != len(rows):
        raise ValueError("MP4 metadata frame count differs from timestamp CSV")
    if camera["fps"] <= 0:
        raise ValueError("Invalid MP4 frame rate")
    return camera


def make_aligned(streams, camera, hz, max_joint_age_ms=50, max_camera_age_ms=200):
    if not 0 < hz <= camera["fps"]:
        raise ValueError("Alignment frequency must be positive and <= head MP4 FPS")
    start = max([int(camera["arrival"][0])]
                + [int(s["arrival"][0]) for s in streams.values()])
    end = min([int(camera["arrival"][-1])]
              + [int(s["arrival"][-1]) for s in streams.values()])
    period_ns = int(round(1e9 / hz))
    if end - start < period_ns:
        raise ValueError("No usable common recording interval")
    grid = start + np.arange((end - start) // period_ns + 1, dtype=np.int64) * period_ns
    arrays = {"timestamp_ns": grid, "time_s": (grid - start) / 1e9}
    chosen = {key: latest_indices(s["arrival"], grid) for key, s in streams.items()}
    for key, s in streams.items():
        idx = chosen[key]
        arrays[key + "_receive_ns"] = s["arrival"][idx]
        arrays[key + "_header_ns"] = s["header"][idx]
        arrays[key + "_age_ms"] = (grid - s["arrival"][idx]) / 1e6
    arrays["state"] = np.concatenate([
        streams[k]["position"][chosen[k]] for k in ("arm_state", "hand_state")], axis=1).astype(np.float32)
    arrays["action"] = np.concatenate([
        streams[k]["position"][chosen[k]] for k in ("arm_command", "hand_command")], axis=1).astype(np.float32)
    for key in ("arm_command", "hand_command"):
        if streams[key]["effort"] is not None:
            arrays[key + "_effort"] = streams[key]["effort"][chosen[key]].astype(np.float32)
    image_idx = latest_indices(camera["arrival"], grid)
    arrays["head_frame_index"] = camera["frame"][image_idx]
    arrays["head_receive_ns"] = camera["arrival"][image_idx]
    arrays["head_header_ns"] = camera["header"][image_idx]
    arrays["head_playback_s"] = arrays["head_frame_index"] / camera["fps"]
    arrays["head_receive_age_ms"] = (grid - arrays["head_receive_ns"]) / 1e6
    arrays["head_capture_age_ms"] = (grid - arrays["head_header_ns"]) / 1e6
    arrays["valid_sample"] = (arrays["head_receive_age_ms"] <= max_camera_age_ms)
    for key in streams:
        arrays["valid_sample"] &= arrays[key + "_age_ms"] <= max_joint_age_ms
    assert arrays["state"].shape == arrays["action"].shape == (len(grid), 13)
    assert np.isfinite(arrays["state"]).all() and np.isfinite(arrays["action"]).all()
    # Image source clocks may differ; causality is checked on availability timestamps.
    for key in ["head", *streams]:
        assert np.all(arrays[key + "_receive_ns"] <= grid)
    return arrays


def stream_summary(stream):
    arrival, header = stream["arrival"], stream["header"]
    good_header = header > 0
    return {
        "messages": len(arrival),
        "receive_hz": float((len(arrival)-1)*1e9/(arrival[-1]-arrival[0]))
                      if arrival[-1] > arrival[0] else None,
        "source_names": [list(row) for row in sorted(stream["source_names"])],
        "first_receive_ns": int(arrival[0]), "last_receive_ns": int(arrival[-1]),
        "header_nonpositive_count": int(np.count_nonzero(~good_header)),
        "header_backwards_count": int(np.count_nonzero(np.diff(header) < 0)),
        "duplicate_receive_count": int(np.count_nonzero(np.diff(arrival) == 0)),
        "max_receive_gap_ms": float(np.max(np.diff(arrival))/1e6) if len(arrival)>1 else None,
        "receive_minus_header_ms": stats((arrival[good_header]-header[good_header])/1e6),
        "position_min": stream["position"].min(axis=0).tolist(),
        "position_max": stream["position"].max(axis=0).tolist(),
        "effort_min": stream["effort"].min(axis=0).tolist() if stream["effort"] is not None else None,
        "effort_max": stream["effort"].max(axis=0).tolist() if stream["effort"] is not None else None,
        "array_lengths": [{"name": k[0], "velocity": k[1], "effort": k[2], "messages": n}
                          for k, n in sorted(stream["aux_lengths"].items())],
    }


def fingerprint(path, full_hash=False):
    item = {"size": path.stat().st_size, "mtime_ns": path.stat().st_mtime_ns}
    if full_hash:
        item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return item


def process_episode(session, root, output, args):
    manifest = json.loads((session / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("outcome") != "success":
        raise ValueError("Episode outcome is not success")
    if manifest.get("side") != "right":
        raise ValueError("Episode side is not right")
    source_files = [session / "manifest.json", session / "video/head.mp4",
                    session / "video/head_timestamps.csv", *sorted((session/"bag").glob("*.db3"))]
    before = {str(p.relative_to(root)): fingerprint(p, p.suffix in (".json", ".csv"))
              for p in source_files}
    streams = read_joint_streams(session)
    camera = read_camera(session)
    arrays = make_aligned(streams, camera, args.hz, args.max_joint_age_ms, args.max_camera_age_ms)
    raw_min = np.concatenate([streams[k]["position"].min(axis=0) for k in ("arm_state", "hand_state")])
    raw_max = np.concatenate([streams[k]["position"].max(axis=0) for k in ("arm_state", "hand_state")])
    cmd_min = np.concatenate([streams[k]["position"].min(axis=0) for k in ("arm_command", "hand_command")])
    cmd_max = np.concatenate([streams[k]["position"].max(axis=0) for k in ("arm_command", "hand_command")])
    warnings = []
    invalid = int(np.count_nonzero(~arrays["valid_sample"]))
    header_gaps = np.diff(camera["header"])/1e6
    header_duplicates = int(np.count_nonzero(np.diff(camera["header"]) == 0))
    header_backwards = int(np.count_nonzero(np.diff(camera["header"]) < 0))
    if header_duplicates or header_backwards:
        warnings.append(f"Camera source stamps repeat={header_duplicates}, backwards={header_backwards}; original frame and receipt order retained")
    if header_gaps.max() > 200:
        warnings.append(f"Camera source frame gap {header_gaps.max():.1f} ms; all original frames retained")
    if invalid:
        warnings.append(f"{invalid} aligned rows have stale data; valid_sample mask must be used by future sequence sampler")
    for key, s in streams.items():
        if np.any(s["header"] <= 0) or np.any(np.diff(s["header"]) < 0):
            warnings.append(f"{key}: source header issue; alignment uses recorder receipt timestamps")
        offset = np.median((s["arrival"]-s["header"])/1e6)
        if abs(offset) > 1000:
            warnings.append(f"{key}: large source-header clock offset {offset:.1f} ms")
    if cmd_min[7:].min() < 0 or cmd_max[7:].max() > 2000:
        warnings.append("Hand command outside SDK nominal 0..2000; not clipped")
    if raw_min[7:].min() < 0 or raw_max[7:].max() > 2000:
        warnings.append("Hand feedback outside nominal 0..2000; zero-offset drift is possible; not clipped")
    video_begin = int(camera["arrival"][0])
    video_end = int(camera["arrival"][-1])
    key = "__".join(session.relative_to(root).parts)
    summary = {
        "episode_id": session.relative_to(root).as_posix(),
        "task": manifest["task"], "outcome": manifest["outcome"],
        "source_session": str(session),
        "source_session_relpath": session.relative_to(root).as_posix(),
        "head_video": str(session / "video/head.mp4"),
        "head_video_relpath": (session.relative_to(root) / "video/head.mp4").as_posix(),
        "source_fingerprints": before,
        "data_file": f"episodes/{key}.npz",
        "aligned_samples": len(arrays["timestamp_ns"]),
        "valid_samples": len(arrays["timestamp_ns"])-invalid,
        "invalid_samples": invalid,
        "alignment_hz": args.hz,
        "first_decision_ns": int(arrays["timestamp_ns"][0]),
        "last_decision_ns": int(arrays["timestamp_ns"][-1]),
        "aligned_span_s": float(arrays["time_s"][-1]),
        "video_start_without_common_coverage_s": max(0, (int(arrays["timestamp_ns"][0])-video_begin)/1e9),
        "video_tail_without_grid_sample_s": max(0, (video_end-int(arrays["timestamp_ns"][-1]))/1e9),
        "camera": {
            "width": camera["width"], "height": camera["height"],
            "fps": camera["fps"], "frames": len(camera["frame"]),
            "playback_duration_s": len(camera["frame"])/camera["fps"],
            "frame_gap_ms": stats(header_gaps),
            "header_duplicate_count": header_duplicates,
            "header_backwards_count": header_backwards,
            "receive_minus_header_ms": stats((camera["arrival"]-camera["header"])/1e6),
            "selected_receive_age_ms": stats(arrays["head_receive_age_ms"]),
            "selected_capture_age_ms": stats(arrays["head_capture_age_ms"]),
            "max_frame_index_used": int(arrays["head_frame_index"].max()),
        },
        "joint_streams": {k: stream_summary(s) for k,s in streams.items()},
        "state_min": raw_min.tolist(), "state_max": raw_max.tolist(),
        "action_min": cmd_min.tolist(), "action_max": cmd_max.tolist(),
        "current_command_feedback_rmse": np.sqrt(np.mean((arrays["action"]-arrays["state"])**2, axis=0)).tolist(),
        "warnings": warnings,
    }
    if summary["video_start_without_common_coverage_s"] > 0.25:
        warnings.append(f"Video starts {summary['video_start_without_common_coverage_s']:.3f} s before all joint streams are available; source video retained, no invented joint observations")
    for p in source_files:
        if before[str(p.relative_to(root))] != fingerprint(p, p.suffix in (".json", ".csv")):
            raise ValueError(f"Source changed while preprocessing: {p}")
    np.savez_compressed(output / "episodes" / f"{key}.npz", **arrays)
    save_json(output / "episodes" / f"{key}.json", summary)
    stride = max(1, int(np.ceil(len(arrays["time_s"])/450)))
    indices = np.unique(np.r_[np.arange(0,len(arrays["time_s"]),stride),len(arrays["time_s"])-1])
    import os
    preview = {
        "id": summary["episode_id"],
        "video": Path(os.path.relpath(session / "video/head.mp4", output)).as_posix(),
        "video_t": np.round(arrays["head_playback_s"][indices],4).tolist(),
        "state": np.round(arrays["state"][indices].astype(np.float64),4).tolist(),
        "action": np.round(arrays["action"][indices].astype(np.float64),4).tolist(),
        "valid": arrays["valid_sample"][indices].tolist(),
        "warnings": warnings,
    }
    return summary, preview


def write_reports(output, summaries, previews, args, failures):
    state_min = np.min([s["state_min"] for s in summaries],axis=0)
    state_max = np.max([s["state_max"] for s in summaries],axis=0)
    action_min = np.min([s["action_min"] for s in summaries],axis=0)
    action_max = np.max([s["action_max"] for s in summaries],axis=0)
    effort_summaries = [s["joint_streams"]["hand_command"] for s in summaries]
    if all(s["effort_min"] is not None for s in effort_summaries):
        effort_min = np.min([s["effort_min"] for s in effort_summaries],axis=0).tolist()
        effort_max = np.max([s["effort_max"] for s in effort_summaries],axis=0).tolist()
    else:
        effort_min, effort_max = None, None
    schema = {
        "format": "a2_right_aligned_v1", "task_id": args.task_id,
        "state_dimension": 13, "action_dimension": 13,
        "channels": [{"index":i,"name":name,"unit":"rad" if i<7 else "hand_abstract_0_2000",
                      "state_range_observed":[float(state_min[i]),float(state_max[i])],
                      "action_range_observed":[float(action_min[i]),float(action_max[i])],
                      "action_constant_in_dataset":bool(action_max[i]-action_min[i]<1e-6)}
                     for i,name in enumerate(CHANNELS)],
        "state_semantics": "measured joint positions; arm then six individual hand channels",
        "action_semantics": "absolute position setpoints recorded from command topics, not feedback or deltas",
        "wrist_semantics": "arm joints 6/7 are equivalent serial coordinates of a parallel wrist",
        "hand_semantics": "SDK abstract positions, nominal 0=open and 2000=closed; actual topic names used; no mean-gripper reduction",
        "normalization": "not fitted: fit on training episodes only after train/validation/test split; guard constant dimensions",
        "effort": "command effort is preserved as auxiliary arrays when present, not part of the 13-D action; audit before deployment",
        "hand_command_effort_observed": {"min":effort_min,"max":effort_max,
            "constant_across_dataset":effort_min == effort_max if effort_min is not None else None,
            "sdk_nominal_range":[0,5700],
            "deployment_note":"Actual values may use firmware-specific conventions. Do not convert, clip, or blindly send them based on this offline schema."},
        "range_warning": "observed ranges are not hardware or deployment safety limits; no clipping applied",
        "image": {"storage":"original head.mp4 + selected frame index", "decode_color":"RGB (OpenCV gives BGR; convert during future image extraction)",
                  "resize_or_crop":"not applied in steps 3/4"},
        "alignment": {
            "hz":args.hz,
            "clock":"ORIN Unix receipt clock: bag timestamp for joints, receive_unix_ns CSV for video",
            "selection":"latest received value <= decision time for every component (zero-order hold)",
            "source_timestamps":"retained separately for latency/clock diagnostics; no assumed constant 81ms correction",
            "interval":"common coverage of all five streams; no semantic trimming or padding",
            "max_joint_receive_age_ms":args.max_joint_age_ms,
            "max_camera_receive_age_ms":args.max_camera_age_ms,
            "stale_samples":"retained with valid_sample=False; future temporal windows must not cross them",
            "integer_nanoseconds":True,
        },
        "sources":{"arm_state":TOPICS["arm_state"],"hand_state":TOPICS["hand_state"],
                   "arm_command":TOPICS["arm_command"],"hand_command":TOPICS["hand_command"],
                   "sdk":DOC_URL},
    }
    save_json(output/"joint_schema.json",schema)
    index = {
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "format":"a2_right_aligned_v1", "source_root":str(args.root),
        "task_id":args.task_id,
        "episode_count":len(summaries),
        "aligned_samples":sum(s["aligned_samples"] for s in summaries),
        "valid_samples":sum(s["valid_samples"] for s in summaries),
        "invalid_samples":sum(s["invalid_samples"] for s in summaries),
        "head_frames":sum(s["camera"]["frames"] for s in summaries),
        "alignment_hz":args.hz,
        "episodes":[{k:s[k] for k in ("episode_id","data_file","aligned_samples","valid_samples","invalid_samples","head_video","head_video_relpath","warnings")}
                    for s in summaries],
        "failures":failures,
        "next_stage":"split by episode, fit training-only normalizers, decode selected RGB frames and create training dataset",
    }
    save_json(output/"dataset_index.json",index)
    with (output/"joint_ranges.csv").open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.writer(f)
        writer.writerow(["index","joint","unit","state_min","state_max","action_min","action_max","action_constant"])
        for i,name in enumerate(CHANNELS):
            writer.writerow([i,name,schema["channels"][i]["unit"],state_min[i],state_max[i],action_min[i],action_max[i],schema["channels"][i]["action_constant_in_dataset"]])
    with (output/"episode_quality.csv").open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.writer(f)
        writer.writerow(["episode_id","aligned_samples","valid_samples","invalid_samples","span_s","camera_receive_header_median_ms","camera_max_source_gap_ms","start_coverage_loss_s","tail_grid_loss_s","warnings"])
        for s in summaries:
            writer.writerow([s["episode_id"],s["aligned_samples"],s["valid_samples"],s["invalid_samples"],s["aligned_span_s"],
                s["camera"]["receive_minus_header_ms"]["median"],s["camera"]["frame_gap_ms"]["max"],
                s["video_start_without_common_coverage_s"],s["video_tail_without_grid_sample_s"],"; ".join(s["warnings"])])
    warning_episodes=sum(bool(s["warnings"]) for s in summaries)
    start_loss_max = max(s["video_start_without_common_coverage_s"] for s in summaries)
    tail_loss_max = max(s["video_tail_without_grid_sample_s"] for s in summaries)
    lines=["# right+：第三、四步处理报告", "",
        f"处理成功 {len(summaries)} 段，失败 {len(failures)} 段。",
        f"10 Hz 对齐行数：{index['aligned_samples']}；新鲜度合格 {index['valid_samples']}，带陈旧数据标记 {index['invalid_samples']}。".replace("10 Hz",f"{args.hz:g} Hz"),
        f"源头部视频帧数 {index['head_frames']}，含检查提示的示教 {warning_episodes} 段。", "",
        "## 观测与动作", "",
        "状态为右臂 7 关节位置反馈＋右手 6 通道位置反馈；动作为相同顺序的目标位置命令，共 13 维。",
        "按关节名称匹配，不按数组最后几项盲取；手臂单位 rad，手指保留 SDK 抽象位置单位。",
        "原始命令 effort 作为辅助数组保留；夹持力是否固定及如何设置，需要在实际控制适配时核对。",
        f"实录右手 command effort 最小值 {effort_min}，最大值 {effort_max}；SDK 文档标称范围为 0～5700，若不一致，保持原始数据并在部署前核对固件和字段单位。",
        "尚未拟合归一化器：划分训练集后仅用训练集计算，避免数据泄漏。", "",
        "## 时间对齐", "",
        "使用同一 ORIN 的接收时钟：关节使用 bag 接收时间，相机使用逐帧 CSV 的 receive_unix_ns。",
        "每个决策时刻选择此前已收到的最新图像、两条反馈和两条命令；不使用未来帧、不做双向插值。",
        "相机拍摄时间、各关节 header 时间均原样保留，用于后续延迟诊断；不把播放器秒数当成 ROS 时间。",
        "仅在五路数据共同覆盖的区间上建立固定频率网格，不裁剪任务过程、不按动作阶段分段。",
        "启动时未获得全部数据的边缘以及不足一个网格周期的尾部在 episode_quality.csv 中单独记录。",
        f"全数据中，视频开头缺少共同关节覆盖最长 {start_loss_max:.6f} 秒，尾部超出共同采样网格最长 {tail_loss_max:.6f} 秒；原始视频完整保留。",
        "valid_sample=False 的行仍保持在原时间位置，后续序列采样不能跨越它们，不能删行后压缩时间轴。", "",
        "## 输出文件", "",
        "- joint_schema.json：固定通道顺序、单位、动作与对齐规则。",
        "- episodes/*.npz：对齐的 state、action、head_frame_index、整数纳秒时间戳及质量掩码。",
        "- episodes/*.json：每段的原始范围、时间戳质量、数据来源指纹和提示。",
        "- joint_ranges.csv：全数据观测/命令数值范围，属于数据统计，不是硬件安全限位。",
        "- episode_quality.csv：每段样本数、源帧间隔和技术性边缘覆盖信息。",
        "- preview.html：用浏览器离线打开，选择视频和关节，查看命令与反馈曲线；它不连接机器人。", "",
        "原始视频不复制、不抽成图片。本阶段用精确帧索引关联视频，后续训练数据转换时再解码 RGB。",
        "已检查 MP4 元信息帧数与 CSV 一致；尚未全量逐帧解码，也未把数据成功标注替换成自动任务评估。", "",
        "## 数值范围", "", "|通道|单位|反馈范围|命令范围|", "|---|---|---|---|"]
    for i,name in enumerate(CHANNELS):
        lines.append(f"|{name}|{'rad' if i<7 else '抽象位置'}|{state_min[i]:.5g} ～ {state_max[i]:.5g}|{action_min[i]:.5g} ～ {action_max[i]:.5g}|")
    lines += ["", "## 逐段提示", ""]
    for s in summaries:
        if s["warnings"]: lines.append(f"- {s['episode_id']}: " + "; ".join(s["warnings"]))
    for s in failures:
        lines.append(f"- FAILED {s['episode_id']}: {s['error']}")
    lines += ["", f"官方字段依据：{DOC_URL}", ""]
    (output/"report.md").write_text("\n".join(lines),encoding="utf-8")
    payload={"channels":CHANNELS,"episodes":previews}
    (output/"preview_data.js").write_text("window.A2_PREVIEW="+json.dumps(payload,ensure_ascii=False,separators=(",",":"),allow_nan=False)+";\n",encoding="utf-8")
    (output/"preview.html").write_text(PREVIEW_HTML,encoding="utf-8")
    return index


PREVIEW_HTML = r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>right+ 数据对齐检查</title><style>
body{font:16px system-ui,sans-serif;margin:24px auto;padding:0 20px;max-width:1100px;color:#203045;background:#f5f7fa}
h1{font-size:25px}select,button{font:inherit;padding:6px;margin:4px}video{width:100%;max-height:470px;background:#111;border-radius:10px}
canvas{width:100%;height:270px;background:white;border:1px solid #ddd;border-radius:10px;cursor:crosshair}
.box{background:white;padding:16px;border-radius:12px;margin:16px 0}.legend{color:#2166bc}.warn{color:#94511b;white-space:pre-wrap}#value{font-variant-numeric:tabular-nums}
</style><h1>right+：视频、右侧关节反馈与命令</h1>
<p>已对齐的真实数据预览。蓝线＝位置反馈，橙线＝目标命令。选择关节后点击曲线可跳转视频；曲线只供检查，不是模型预测。</p>
<div class="box"><label>示教 <select id="episode"></select></label><label>通道 <select id="joint"></select></label><p id="status"></p><video id="video" controls preload="metadata"></video></div>
<div class="box"><p id="value"></p><canvas id="plot"></canvas><p>横轴为所选图像的 MP4 播放秒数；原始接收时间和拍摄时间保存在 NPZ。图像的接收延迟已保留，不能把播放器秒数直接当成决策时钟。</p><p class="warn" id="warn"></p></div>
<script src="preview_data.js"></script><script>
const data=window.A2_PREVIEW,es=document.getElementById('episode'),js=document.getElementById('joint'),v=document.getElementById('video'),c=document.getElementById('plot'),ctx=c.getContext('2d');
data.episodes.forEach((e,i)=>es.add(new Option(e.id,i)));data.channels.forEach((n,i)=>js.add(new Option(`${i}: ${n}`,i)));
let current=data.episodes[0],bounds={};
function draw(){if(!current)return;const j=+js.value,W=c.width=1000,H=c.height=270,p=55,ts=current.video_t;let lo=Infinity,hi=-Infinity;
for(let k=0;k<ts.length;k++){lo=Math.min(lo,current.state[k][j],current.action[k][j]);hi=Math.max(hi,current.state[k][j],current.action[k][j]);}
let margin=Math.max((hi-lo)*.12,j<7?.03:10);lo-=margin;hi+=margin;const end=Math.max(ts[ts.length-1],.1);bounds={end,p,W,H};
const x=t=>p+t/end*(W-2*p),y=a=>H-p-(a-lo)/(hi-lo)*(H-2*p);ctx.clearRect(0,0,W,H);ctx.font='13px sans-serif';ctx.strokeStyle='#dae0e6';ctx.fillStyle='#526070';
for(let i=0;i<=4;i++){const yy=p+i*(H-2*p)/4;ctx.beginPath();ctx.moveTo(p,yy);ctx.lineTo(W-p,yy);ctx.stroke();ctx.fillText((hi-i*(hi-lo)/4).toFixed(j<7?2:0),3,yy+4);ctx.fillText((i*end/4).toFixed(1)+'s',x(i*end/4)-8,H-12);}
for(const [field,color]of[['state','#2166bc'],['action','#df7b20']]){ctx.strokeStyle=color;ctx.lineWidth=2;ctx.beginPath();ts.forEach((t,k)=>{if(k===0)ctx.moveTo(x(t),y(current[field][k][j]));else ctx.lineTo(x(t),y(current[field][k][j]));});ctx.stroke();}
ctx.strokeStyle='#263343';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(x(v.currentTime),p);ctx.lineTo(x(v.currentTime),H-p);ctx.stroke();
let k=0;while(k+1<ts.length&&ts[k+1]<=v.currentTime)k++;document.getElementById('value').textContent=`${data.channels[j]}：反馈 ${current.state[k][j].toFixed(4)}；命令 ${current.action[k][j].toFixed(4)}；${j<7?'rad':'手指抽象位置'}；该预览采样点 ${current.valid[k]?'新鲜度合格':'含陈旧数据标记'}`;}
function choose(){current=data.episodes[+es.value];v.src=current.video;document.getElementById('status').textContent=current.id;document.getElementById('warn').textContent=current.warnings.join('\n');draw();}
es.onchange=choose;js.onchange=draw;v.ontimeupdate=draw;v.onloadedmetadata=draw;c.onclick=e=>{const r=c.getBoundingClientRect(),x=(e.clientX-r.left)/r.width*bounds.W;v.currentTime=Math.max(0,Math.min(bounds.end,(x-bounds.p)/(bounds.W-2*bounds.p)*bounds.end));draw();};choose();
</script></html>'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=Path("data/right/right+"))
    parser.add_argument("--out",type=Path,default=Path("processed/right_plus_step34"))
    parser.add_argument("--hz",type=float,default=10)
    parser.add_argument("--task-id",default="right_plus_stack_cubes")
    parser.add_argument("--max-joint-age-ms",type=float,default=50)
    parser.add_argument("--max-camera-age-ms",type=float,default=200)
    parser.add_argument("--limit",type=int,help="Only for pipeline checks; normal runs process every episode")
    args=parser.parse_args()
    args.root=args.root.expanduser().resolve();args.out=args.out.expanduser().resolve()
    if args.out==args.root or args.root in args.out.parents:
        parser.error("Output must be outside the raw input tree")
    if args.out.exists() and any(args.out.iterdir()):
        parser.error("Output directory is nonempty; choose a new output path")
    if args.hz<=0 or args.max_joint_age_ms<=0 or args.max_camera_age_ms<=0:
        parser.error("Frequency and age thresholds must be positive")
    paths=sorted(args.root.rglob("manifest.json"))
    if args.limit is not None:
        if args.limit<=0: parser.error("--limit must be positive")
        paths=paths[:args.limit]
    if not paths: parser.error("No manifests found")
    observed_tasks={json.loads(p.read_text(encoding="utf-8")).get("task") for p in paths}
    if observed_tasks != {args.task_id}:
        parser.error(f"Input tasks {observed_tasks} do not match --task-id {args.task_id}; do not mix right+ and right-")
    (args.out/"episodes").mkdir(parents=True)
    summaries,previews,failures=[],[],[]
    for i,path in enumerate(paths,1):
        try:
            summary,preview=process_episode(path.parent,args.root,args.out,args)
            summaries.append(summary);previews.append(preview)
            print(f"[{i}/{len(paths)}] {summary['episode_id']}: {summary['aligned_samples']} rows, stale={summary['invalid_samples']}",flush=True)
        except Exception as exc:
            failures.append({"episode_id":path.parent.relative_to(args.root).as_posix(),"error":str(exc)})
            print(f"[{i}/{len(paths)}] FAILED {path.parent}: {exc}",file=sys.stderr,flush=True)
    if not summaries:
        save_json(args.out/"failures.json",failures)
        return 2
    index=write_reports(args.out,summaries,previews,args,failures)
    print(json.dumps({k:index[k] for k in ("episode_count","aligned_samples","valid_samples","invalid_samples")},ensure_ascii=False),flush=True)
    print(f"Report: {args.out/'report.md'}",flush=True)
    return 2 if failures else 0


if __name__=="__main__":
    sys.exit(main())
