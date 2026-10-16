#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import JointState


class HandPublisher(Node):
    def __init__(self, hand_topic_name: str):
        super().__init__("hand_publisher")

        qos_profile = QoSProfile(
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
        )

        self.publisher = self.create_publisher(JointState, hand_topic_name, qos_profile)

        timer_period = 0.02
        self.timer = self.create_timer(timer_period, self.timer_callback)

    def timer_callback(self):
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()

        # 必须正确传入所有手指的关节名称
        msg.name = [
            "L_thumb_swing_joint",
            "L_thumb_1_joint",
            "L_index_1_joint",
            "L_middle_1_joint",
            "L_ring_1_joint",
            "L_little_1_joint",
            "R_thumb_swing_joint",
            "R_thumb_1_joint",
            "R_index_1_joint",
            "R_middle_1_joint",
            "R_ring_1_joint",
            "R_little_1_joint",
        ]

        # 手指位置，范围 0-2000，必选
        left_finger_positions = [0.0, 1000.0, 2000.0, 2000.0, 2000.0, 2000.0]
        right_finger_positions = [0.0, 1000.0, 2000.0, 2000.0, 2000.0, 2000.0]

        # 手指扭矩，范围 0-5700，必选
        left_finger_torques = [2000.0, 2000.0, 2000.0, 2000.0, 2000.0, 2000.0]
        right_finger_torques = [2000.0, 2000.0, 2000.0, 2000.0, 2000.0, 2000.0]

        # 将位置和力矩拼接起来
        msg.position = left_finger_positions + right_finger_positions
        msg.effort = left_finger_torques + right_finger_torques

        self.publisher.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    hand_publisher = HandPublisher("/motion/control/hand_joint_command")
    try:
        rclpy.spin(hand_publisher)
    except KeyboardInterrupt:
        pass
    finally:
        hand_publisher.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
