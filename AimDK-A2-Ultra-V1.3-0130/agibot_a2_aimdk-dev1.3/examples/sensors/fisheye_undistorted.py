#!/usr/bin/env python3

"""
- Purpose: To undistort fisheye camera images and \
    save the original image alongside the undistorted image side by side to a specified directory

- Adjustable Parameters:
  - yaml_path: Path to the camera intrinsic YAML file.
  - topic_name: Subscribed ROS Image topic.
  - out_dir: Directory where results are saved.
  - balance: Balance parameter during undistortion（controls field of view cropping/retention, default is 0.0）
  - focal_scale: Focal length scaling factor for the new camera matrix (default is 2.0)

- Example of Running:
  python3 fisheye_undistorted.py
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
from rclpy.qos import QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
import cv2
import numpy as np
import yaml
import os
import queue
import threading
from datetime import datetime
import time


class FisheyeUndistorter(Node):
    def __init__(self, yaml_path: str, topic_name: str, out_dir: str):
        super().__init__("fisheye_undistorter")
        self.bridge = CvBridge()

        self.topic_name = topic_name
        self.out_dir = out_dir
        os.makedirs(self.out_dir, exist_ok=True)

        self.latest_img = None
        self.img_lock = threading.Lock()

        self.K, self.D, (self.width, self.height) = self.load_fisheye_yaml(yaml_path)
        self.map1, self.map2 = self.init_undistort_maps(balance=0.0, focal_scale=2.0)

        self.save_q: queue.Queue = queue.Queue(maxsize=10)
        self.stop_evt = threading.Event()

        self.undistort_thr = threading.Thread(target=self.undistort_loop, daemon=True)
        self.undistort_thr.start()
        self.writer_thr = threading.Thread(target=self.writer_loop, daemon=True)
        self.writer_thr.start()

        qos_profile = QoSProfile(
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
        )

        self.subscription = self.create_subscription(
            Image, topic_name, self.listener_callback, qos_profile
        )

        self.get_logger().info(
            f"Started. topic={topic_name}, yaml={yaml_path}, out_dir={out_dir}"
        )

    def load_fisheye_yaml(self, path):
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
        K = np.array(
            [[p["mu"], 0, p["u0"]], [0, p["mv"], p["v0"]], [0, 0, 1]], dtype=np.float32
        )
        D = np.array([p["k2"], p["k3"], p["k4"], p["k5"]], dtype=np.float32)

        dims = (data["image_width"], data["image_height"])
        return K, D, dims

    def init_undistort_maps(self, balance=0.0, focal_scale=2.0):
        new_K = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
            self.K, self.D, (self.width, self.height), np.eye(3), balance=balance
        )
        new_K[0, 0] *= focal_scale
        new_K[1, 1] *= focal_scale
        new_K[0, 2] = self.width / 2
        new_K[1, 2] = self.height / 2

        map1, map2 = cv2.fisheye.initUndistortRectifyMap(
            self.K, self.D, np.eye(3), new_K, (self.width, self.height), cv2.CV_16SC2
        )
        return map1, map2

    def listener_callback(self, msg):
        try:
            cv_img = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            with self.img_lock:
                self.latest_img = cv_img
        except Exception as e:
            self.get_logger().error(f"Callback error: {e}")

    def undistort_loop(self):
        period = 1.0

        while not self.stop_evt.is_set():
            raw_img = None
            with self.img_lock:
                if self.latest_img is not None:
                    raw_img = self.latest_img.copy()

            if raw_img is not None:
                undistorted = cv2.remap(
                    raw_img,
                    self.map1,
                    self.map2,
                    interpolation=cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_CONSTANT,
                )
                combined = np.hstack((raw_img, undistorted))

                ts_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                try:
                    self.save_q.put_nowait((combined, ts_str))
                except queue.Full:
                    pass

            time.sleep(period)

    def writer_loop(self):
        while not self.stop_evt.is_set():
            try:
                combined, ts_str = self.save_q.get(timeout=0.2)
                filename = os.path.join(self.out_dir, f"fisheye_{ts_str}.jpg")
                ok = cv2.imwrite(filename, combined)

                if not ok:
                    self.get_logger().error(f"Failed to save: {filename}")

            except queue.Empty:
                continue
            except Exception as e:
                self.get_logger().error(f"Writer thread error: {e}")

    def destroy_node(self):
        self.stop_evt.set()
        try:
            self.undistort_thr.join(timeout=1.0)
            self.writer_thr.join(timeout=1.0)
        except Exception:
            pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)

    yaml_path = "/agibot/data/param/calibration/intrinsic_chest_left.yaml"
    topic_name = "/aima/hal/fish_eye_camera/chest_left/color"
    out_dir = "./output_images/fisheye_undistorted"

    node = FisheyeUndistorter(yaml_path, topic_name, out_dir)

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
