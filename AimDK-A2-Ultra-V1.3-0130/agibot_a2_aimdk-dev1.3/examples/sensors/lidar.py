#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import Imu, PointCloud2


class LidarSubscriber(Node):
    def __init__(self, point_cloud_topic_name: str, imu_topic_name: str):
        super().__init__("lidar_subscriber")

        self.point_cloud_topic_name = point_cloud_topic_name
        self.imu_topic_name = imu_topic_name

        qos_profile = QoSProfile(
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
        )

        self.point_cloud_subscription = self.create_subscription(
            PointCloud2,
            point_cloud_topic_name,
            self.point_cloud_listener_callback,
            qos_profile,
        )
        # self.imu_subscription = self.create_subscription(
        #     Imu, imu_topic_name, self.imu_listener_callback, qos_profile
        # )

    def point_cloud_listener_callback(self, msg: PointCloud2):
        self.get_logger().info(f"=== Received {self.point_cloud_topic_name} ===")
        self.get_logger().info(f"  header: {msg.header}")
        self.get_logger().info(f"  height: {msg.height}")
        self.get_logger().info(f"  width: {msg.width}")
        self.get_logger().info(f"  fields: {msg.fields}")
        self.get_logger().info(f"  is_bigendian: {msg.is_bigendian}")
        self.get_logger().info(f"  point_step: {msg.point_step}")
        self.get_logger().info(f"  row_step: {msg.row_step}")
        self.get_logger().info(f"  data length: {len(msg.data)}")
        self.get_logger().info(f"  is_dense: {msg.is_dense}")

    def imu_listener_callback(self, msg: Imu):
        self.get_logger().info(f"=== Received {self.imu_topic_name} ===")
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
    lidar_node = LidarSubscriber(
        "/aima/hal/lidar/neck/pointcloud", "/aima/hal/lidar/neck/imu"
    )
    try:
        rclpy.spin(lidar_node)
    except KeyboardInterrupt:
        pass
    finally:
        lidar_node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
