#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import JointState


class NeckPublisher(Node):
    def __init__(self, neck_topic_name: str):
        super().__init__("neck_publisher")

        qos_profile = QoSProfile(
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
        )

        self.publisher = self.create_publisher(JointState, neck_topic_name, qos_profile)

        timer_period = 0.02
        self.timer = self.create_timer(timer_period, self.timer_callback)

    def timer_callback(self):
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()

        # 仅支持位控
        # 第一个值代表摇头，范围 -0.785 - 0.785
        # 第二个值代表点头，范围 -0.401 - 0.401
        msg.name = ["idx27_head_joint1", "idx28_head_joint2"]
        msg.position = [0.5, 0.5]

        # 以下字段无实际作用，但必须设置，否则可能导致运控 crash
        msg.velocity = [0.0, 0.0]
        msg.effort = [0.0, 0.0]

        self.publisher.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    neck_publisher = NeckPublisher("/motion/control/neck_joint_command")
    try:
        rclpy.spin(neck_publisher)
    except KeyboardInterrupt:
        pass
    finally:
        neck_publisher.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
