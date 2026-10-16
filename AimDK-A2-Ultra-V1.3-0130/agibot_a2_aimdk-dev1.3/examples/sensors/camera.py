#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import Image


class ImageSubscriber(Node):
    def __init__(self, topic_name: str):
        super().__init__("image_subscriber")

        self.topic_name = topic_name

        qos_profile = QoSProfile(
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
        )

        self.subscription = self.create_subscription(
            Image, topic_name, self.listener_callback, qos_profile
        )
        self.subscription

    def listener_callback(self, msg: Image):
        self.get_logger().info(f"=== Received {self.topic_name} ===")
        self.get_logger().info(f"  header: {msg.header}")
        self.get_logger().info(f"  width: {msg.width}")
        self.get_logger().info(f"  height: {msg.height}")
        self.get_logger().info(f"  encoding: {msg.encoding}")
        self.get_logger().info(f"  is_bigendian: {msg.is_bigendian}")
        self.get_logger().info(f"  step: {msg.step}")
        self.get_logger().info(f"  data length: {len(msg.data)}")


def main(args=None):
    rclpy.init(args=args)
    # 头部相机 color: /aima/hal/rgbd_camera/head_front/color
    # 头部相机 depth: /aima/hal/rgbd_camera/head_front/depth
    # 髋部相机 color: /aima/hal/rgbd_camera/waist_front/color
    # 髋部相机 depth: /aima/hal/rgbd_camera/waist_front/depth
    # 胸部左侧相机 color: /aima/hal/fish_eye_camera/chest_left/color
    # 胸部右侧相机 color: /aima/hal/fish_eye_camera/chest_right/color
    # 胸部中间相机 color: /aima/hal/camera/interactive/color
    image_node = ImageSubscriber("/aima/hal/fish_eye_camera/chest_right/color")
    try:
        rclpy.spin(image_node)
    except KeyboardInterrupt:
        pass
    finally:
        image_node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
