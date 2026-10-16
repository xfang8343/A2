"""Focused tests for joint identity, integer timestamps and causal alignment."""
import struct
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np

from a2_prepare_right import (ARM_NAMES, canonical_name, latest_indices,
                              make_aligned, parse_joint, read_camera, right_indices)


def encode_joint(names, values, base):
    data = bytearray(b"\x00\x01\x00\x00")

    def fixed(fmt, value, alignment):
        data.extend(b"\x00" * (-(len(data) - base) % alignment))
        data.extend(struct.pack("<" + fmt, value))

    def string(value):
        raw = value.encode() + b"\x00"
        fixed("I", len(raw), 4)
        data.extend(raw)

    fixed("i", 1791428922, 4)
    fixed("I", 123456789, 4)
    string("")
    fixed("I", len(names), 4)
    for name in names:
        string(name)
    fixed("I", len(values), 4)
    for value in values:
        fixed("d", value, 8)
    fixed("I", 0, 4)
    fixed("I", 0, 4)
    return bytes(data)


class AlignmentTests(unittest.TestCase):
    def test_joint_names_not_array_position(self):
        names = ["idx26_right_arm_joint7", "idx13_left_arm_joint1"] + [
            f"idx{19+i}_right_arm_joint{i}" for i in range(1, 7)]
        indices = right_indices(names, "arm")
        self.assertEqual([canonical_name(names[i]) for i in indices], ARM_NAMES)
        with self.assertRaises(ValueError):
            right_indices(names + ["right_arm_joint1"], "arm")

    def test_hand_sdk_aliases(self):
        names = ["R_little_1_joint", "R_ring_1_joint", "R_middle_1_joint",
                 "R_index_1_joint", "R_thumb_1_joint", "R_thumb_swing_joint"]
        self.assertEqual(right_indices(names, "hand"), [5, 4, 3, 2, 1, 0])

    def test_cdr_alignment_forms(self):
        names = ["idx20_right_arm_joint1", "idx21_right_arm_joint2"]
        for base in [4, 0]:
            data = encode_joint(names, [1.234, -0.456], base)
            parsed = parse_joint(data)
            self.assertEqual(parsed[1], 1791428922123456789)
            np.testing.assert_allclose(parsed[3], [1.234, -0.456])

    def test_duplicate_capture_stamp_retains_frames(self):
        class Capture:
            def __init__(self, *args): pass
            def isOpened(self): return True
            def get(self, key):
                import cv2
                return {cv2.CAP_PROP_FRAME_WIDTH:1280,cv2.CAP_PROP_FRAME_HEIGHT:720,
                        cv2.CAP_PROP_FPS:15,cv2.CAP_PROP_FRAME_COUNT:2}[key]
            def release(self): pass
        with TemporaryDirectory() as folder:
            session=Path(folder); (session/'video').mkdir()
            stamps=session/'video/head_timestamps.csv'
            stamps.write_text('frame_index,header_stamp_ns,receive_unix_ns\n0,100,200\n1,100,300\n')
            with patch('a2_prepare_right.cv2.VideoCapture',Capture):
                camera=read_camera(session)
                self.assertEqual(camera['frame'].tolist(),[0,1])
                stamps.write_text('frame_index,header_stamp_ns,receive_unix_ns\n0,100,300\n1,100,200\n')
                with self.assertRaises(ValueError): read_camera(session)

    def test_latest_integer_ns_does_not_round_epoch(self):
        origin = 1791428922000000000
        messages = np.array([origin, origin+1, origin+2], dtype=np.int64)
        query = np.array([origin+1], dtype=np.int64)
        self.assertEqual(latest_indices(messages, query).tolist(), [1])

    def test_receipt_causality_staleness_and_command_hold(self):
        origin = 1791428922000000000
        arrivals = origin + np.arange(31, dtype=np.int64)*10_000_000
        streams = {}
        for key, width in [("arm_state",7),("hand_state",6),
                           ("arm_command",7),("hand_command",6)]:
            positions = np.arange(31, dtype=np.float64)[:,None] * np.ones((1,width))
            streams[key] = {"arrival":arrivals,"header":arrivals-1_000_000,
                            "position":positions,"effort":None}
        # Frame 2 was captured before 200ms but did not arrive until 210ms.
        camera_arrivals = origin + np.array([0,90,210,300],dtype=np.int64)*1_000_000
        camera = {"arrival":camera_arrivals,"header":camera_arrivals-80_000_000,
                  "frame":np.arange(4),"fps":15}
        output = make_aligned(streams,camera,10,max_camera_age_ms=100)
        self.assertEqual(output["head_frame_index"].tolist(),[0,1,1,3])
        self.assertEqual(output["valid_sample"].tolist(),[True,True,False,True])
        np.testing.assert_allclose(output["action"][:,0],[0,10,20,30])
        for key in ["head",*streams]:
            self.assertTrue(np.all(output[key+"_receive_ns"] <= output["timestamp_ns"]))
        self.assertEqual(output["state"].shape,(4,13))


if __name__ == "__main__":
    unittest.main()
