#!/usr/bin/env python3

import json
from datetime import datetime

import rclpy
from actions import get_action
from rclpy.node import Node
from rclpy.qos import QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from ros2_plugin_proto.msg import RosMsgWrapper


def create_header() -> dict:
    now = datetime.utcnow()
    return {
        "timestamp": {
            "seconds": int(now.timestamp()),
            "nanos": now.microsecond * 1000,
            "ms_since_epoch": int(now.timestamp() * 1000),
        },
        "control_source": "ControlSource_MANUAL",
    }


class MoveWaistPublisher(Node):
    def __init__(self, move_waist_topic_name: str):
        super().__init__("move_waist_publisher")

        qos_profile = QoSProfile(
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
        )

        self.publisher = self.create_publisher(
            RosMsgWrapper, move_waist_topic_name, qos_profile
        )

        timer_period = 0.05  # 20 Hz, matches legacy T_MoveWaist script cadence
        self.timer = self.create_timer(timer_period, self.timer_callback)

        self.pose_sequences = self._build_pose_sequences()
        self.repeat_per_pose = 70
        self.max_publications = len(self.pose_sequences) * self.repeat_per_pose
        self.publications_count = 0
        self.current_sequence_index = 0
        self.current_repeat_count = 0

        self.get_logger().info(
            f"Publisher will send {self.max_publications} poses ({len(self.pose_sequences)} unique keyframes).",
        )

    @staticmethod
    def _build_pose_sequences() -> list[dict]:
        x = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        y = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        z = [-0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        roll = [0.0, 0.0, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0]
        pitch = [0.0, 0.0, 0.0, 0.0, 0.1, 0.0, 0.0, 0.0]
        yaw = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5, 0.0]

        sequences = []
        for idx in range(len(x)):
            sequences.append(
                {
                    "x": x[idx],
                    "y": y[idx],
                    "z": z[idx],
                    "roll": roll[idx],
                    "pitch": pitch[idx],
                    "yaw": yaw[idx],
                }
            )
        return sequences

    def timer_callback(self):
        if self.current_sequence_index >= len(self.pose_sequences):
            self.get_logger().info(
                "All waist poses have been published. Stopping publisher."
            )
            self.timer.cancel()
            self.destroy_node()
            return

        pose = self.pose_sequences[self.current_sequence_index]
        payload = {
            "header": create_header(),
            "data": pose,
        }

        json_bytes = json.dumps(payload).encode("utf-8")

        msg = RosMsgWrapper()
        msg.serialization_type = "json"
        msg.data = [bytes([byte]) for byte in json_bytes]

        self.publisher.publish(msg)
        self.publications_count += 1
        self.current_repeat_count += 1

        if self.current_repeat_count >= self.repeat_per_pose:
            self.current_sequence_index += 1
            self.current_repeat_count = 0

        if self.publications_count >= self.max_publications:
            self.get_logger().info(
                "Reached %d publications. Cancelling timer and destroying node.",
                self.max_publications,
            )
            self.timer.cancel()
            self.destroy_node()
            return


def main(args=None):
    mc_ip = "192.168.100.100"
    current_action = get_action(mc_ip=mc_ip)
    allowed_actions = [
        "McAction_RL_WHOLE_BODY_EXT_JOINT_SERVO",
    ]
    if current_action not in allowed_actions:
        print(
            f"Current action: {current_action} is not allowed, please set to one of the following: {allowed_actions}"
        )
        return

    rclpy.init(args=args)
    move_waist_publisher = MoveWaistPublisher(
        "/motion/control/move_waist/pb_3Aaimdk_2Eprotocol_2EMcMoveWaistChannel",
    )
    try:
        rclpy.spin(move_waist_publisher)
    except KeyboardInterrupt:
        pass
    finally:
        move_waist_publisher.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
