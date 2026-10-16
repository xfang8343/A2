#!/usr/bin/env python3

"""
- Purpose: To align depth images to the color image viewpoint, generate a visualization image, and save it to a specified directory.

- Adjustable Parameters:
  - yaml_path: Path to the camera intrinsic YAML file.
  - color_topic: ROS Image topic for color images.
  - depth_topic: ROS Image topic for depth images.
  - out_dir: Directory where results are saved.
  - baseline_x: Baseline offset in the x direction for depth (can be used to adjust disparity, default is 0).

- Example of Running:
  python3 rgbd_align.py
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import numpy as np
import message_filters
import yaml
import os
import queue
import threading
from datetime import datetime
import time


class D2rAligner(Node):
    def __init__(
        self, yaml_path: str, color_topic: str, depth_topic: str, out_dir: str
    ):
        super().__init__("d2r_aligner")
        self.bridge = CvBridge()

        self.color_topic = color_topic
        self.depth_topic = depth_topic
        self.out_dir = out_dir
        os.makedirs(self.out_dir, exist_ok=True)

        self.intrinsics = self.load_yaml(yaml_path)
        self.baseline_x = 0

        self.latest_rgb = None
        self.latest_depth = None
        self.data_lock = threading.Lock()

        self.save_q: queue.Queue = queue.Queue(maxsize=10)
        self.stop_evt = threading.Event()

        self.align_thr = threading.Thread(target=self.align_loop, daemon=True)
        self.align_thr.start()
        self.writer_thr = threading.Thread(target=self.writer_loop, daemon=True)
        self.writer_thr.start()

        qos_profile = QoSProfile(
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
        )

        self.color_sub = message_filters.Subscriber(
            self, Image, color_topic, qos_profile=qos_profile
        )
        self.depth_sub = message_filters.Subscriber(
            self, Image, depth_topic, qos_profile=qos_profile
        )

        self.ts = message_filters.ApproximateTimeSynchronizer(
            [self.color_sub, self.depth_sub], 10, 0.05
        )
        self.ts.registerCallback(self.callback)

        self.get_logger().info(
            f"Aligner started. color={color_topic}, depth={depth_topic}"
        )

    def load_yaml(self, path):
        with open(path, "r") as f:
            first_line = f.readline().strip()

            if first_line != "%YAML:1.0":
                error_msg = (
                    f"YAML Error: Expected header '%YAML:1.0', but found '{first_line}'"
                )
                self.get_logger().error(error_msg)
                raise ValueError(error_msg)

            content = f.read()
            data = yaml.safe_load(content)

        p = data["projection_parameters"]
        return {
            "w": data["image_width"],
            "h": data["image_height"],
            "fx": p["fx"],
            "fy": p["fy"],
            "cx": p["cx"],
            "cy": p["cy"],
        }

    def align_logic(self, depth_img):
        h, w = depth_img.shape
        fx, fy = self.intrinsics["fx"], self.intrinsics["fy"]
        cx, cy = self.intrinsics["cx"], self.intrinsics["cy"]

        u, v = np.meshgrid(np.arange(w), np.arange(h))

        z = depth_img.astype(np.float32) / 1000.0
        valid_mask = z > 0.1
        z_safe = np.where(valid_mask, z, 1.0)

        x = (u - cx) * z / fx
        y = (v - cy) * z / fy

        x_new = x + self.baseline_x

        u_new = (x_new * fx / z_safe + cx).astype(np.int32)
        v_new = (y * fy / z_safe + cy).astype(np.int32)

        aligned_depth = np.zeros_like(depth_img)
        in_view = (u_new >= 0) & (u_new < w) & (v_new >= 0) & (v_new < h) & valid_mask

        aligned_depth[v_new[in_view], u_new[in_view]] = depth_img[in_view]

        return aligned_depth

    def callback(self, color_msg, depth_msg):
        try:
            cv_rgb = self.bridge.imgmsg_to_cv2(color_msg, desired_encoding="bgr8")
            cv_depth = self.bridge.imgmsg_to_cv2(
                depth_msg, desired_encoding="passthrough"
            )

            with self.data_lock:
                self.latest_rgb = cv_rgb
                self.latest_depth = cv_depth

        except Exception as e:
            self.get_logger().error(f"Callback error: {e}")

    def align_loop(self):
        period = 1.0

        while not self.stop_evt.is_set():
            rgb = None
            depth = None
            with self.data_lock:
                if self.latest_rgb is not None and self.latest_depth is not None:
                    rgb = self.latest_rgb.copy()
                    depth = self.latest_depth.copy()

            if rgb is not None and depth is not None:
                aligned_depth = self.align_logic(depth)

                depth_vis = cv2.normalize(
                    aligned_depth, None, 0, 255, cv2.NORM_MINMAX, cv2.CV_8U
                )
                depth_color = cv2.applyColorMap(depth_vis, cv2.COLORMAP_JET)

                edges = cv2.Canny(cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY), 100, 200)
                depth_color[edges > 0] = (255, 255, 255)

                overlap = cv2.addWeighted(rgb, 0.6, depth_color, 0.4, 0)
                ts_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]

                try:
                    self.save_q.put_nowait((overlap, ts_str))
                except queue.Full:
                    pass

            time.sleep(period)

    def writer_loop(self):
        while not self.stop_evt.is_set():
            try:
                img, ts_str = self.save_q.get(timeout=0.2)
                filename = os.path.join(self.out_dir, f"align_{ts_str}.jpg")

                ok = cv2.imwrite(filename, img)
                if not ok:
                    self.get_logger().error(f"Failed to save {filename}")

            except queue.Empty:
                continue
            except Exception as e:
                self.get_logger().error(f"Writer error: {e}")

    def destroy_node(self):
        self.stop_evt.set()
        try:
            self.align_thr.join(timeout=1.0)
            self.writer_thr.join(timeout=1.0)
        except Exception:
            pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)

    yaml_path = "/agibot/data/param/calibration/intrinsic_head_front.yaml"
    color_topic = "/aima/hal/rgbd_camera/head_front/color"
    depth_topic = "/aima/hal/rgbd_camera/head_front/depth"
    out_dir = "./output_images/d2r_aligned"

    node = D2rAligner(yaml_path, color_topic, depth_topic, out_dir)

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
