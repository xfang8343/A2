#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import Imu


class ImuSubscriber(Node):
    def __init__(self, topic_name: str):
        super().__init__("imu_subscriber")

        self.topic_name = topic_name

        qos_profile = QoSProfile(
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
        )

        self.subscription = self.create_subscription(
            Imu, topic_name, self.listener_callback, qos_profile
        )
        self.subscription

    def listener_callback(self, msg: Imu):
        self.get_logger().info(f"=== Received {self.topic_name} ===")
        self.get_logger().info(f"  header: {msg.header}")
        self.get_logger().info(f"  orientation: {msg.orientation}")
        self.get_logger().info(
            f"  orientation_covariance: {msg.orientation_covariance}"
        )
        self.get_logger().info(f"  angular_velocity: {msg.angular_velocity}")
        self.get_logger().info(
            f"  angular_velocity_covariance: {msg.angular_velocity_covariance}"
        )
        self.get_logger().info(f"  linear_acceleration: {msg.linear_acceleration}")
        self.get_logger().info(
            f"  linear_acceleration_covariance: {msg.linear_acceleration_covariance}"
        )


def main(args=None):
    rclpy.init(args=args)
    imu_node = ImuSubscriber("/body_drive/imu/data")
    try:
        rclpy.spin(imu_node)
    except KeyboardInterrupt:
        pass
    finally:
        imu_node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
