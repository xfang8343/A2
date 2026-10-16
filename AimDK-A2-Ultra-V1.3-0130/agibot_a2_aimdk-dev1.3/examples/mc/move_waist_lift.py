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


class MoveWaistLiftPublisher(Node):
    def __init__(self, move_waist_lift_topic_name: str):
        super().__init__("move_waist_lift_publisher")

        qos_profile = QoSProfile(
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
        )

        self.publisher = self.create_publisher(
            RosMsgWrapper, move_waist_lift_topic_name, qos_profile
        )

        timer_period = 0.05  # 20 Hz, aligns with the legacy script cadence
        self.timer = self.create_timer(timer_period, self.timer_callback)

        self.lift_sequences = self._build_lift_sequences()
        self.repeat_per_value = 70
        self.max_publications = len(self.lift_sequences) * self.repeat_per_value
        self.publications_count = 0
        self.current_sequence_index = 0
        self.current_repeat_count = 0

        self.get_logger().info(
            f"Publisher will send {self.max_publications} lift commands ({len(self.lift_sequences)} unique values).",
        )

    @staticmethod
    def _build_lift_sequences() -> list[float]:
        return [-0.1, 0.0]

    def timer_callback(self):
        if self.current_sequence_index >= len(self.lift_sequences):
            self.get_logger().info(
                "All waist lift commands have been published. Stopping publisher."
            )
            self.timer.cancel()
            self.destroy_node()
            return

        lift_value = self.lift_sequences[self.current_sequence_index]
        payload = {
            "header": create_header(),
            "waist_lift_value": lift_value,
        }

        json_bytes = json.dumps(payload).encode("utf-8")

        msg = RosMsgWrapper()
        msg.serialization_type = "json"
        msg.data = [bytes([byte]) for byte in json_bytes]

        self.publisher.publish(msg)
        self.publications_count += 1
        self.current_repeat_count += 1

        if self.current_repeat_count >= self.repeat_per_value:
            self.current_sequence_index += 1
            self.current_repeat_count = 0

        if self.publications_count >= self.max_publications:
            self.get_logger().info(
                f"Reached {self.max_publications} publications. Cancelling timer and destroying node.",
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
    move_waist_lift_publisher = MoveWaistLiftPublisher(
        "/motion/control/move_waist_lift/pb_3Aaimdk_2Eprotocol_2EMcMoveWaistLiftChannel",
    )
    try:
        rclpy.spin(move_waist_lift_publisher)
    except KeyboardInterrupt:
        pass
    finally:
        move_waist_lift_publisher.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
