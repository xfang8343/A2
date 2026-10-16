#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from ros2_plugin_proto.msg import RosMsgWrapper

from aimdk.protocol_pb2 import FaceIdResult


class FaceIdSubscriber(Node):
    def __init__(self):
        super().__init__("face_id_subscriber")

        qos_profile = QoSProfile(
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
        )

        self.subscription = self.create_subscription(
            RosMsgWrapper,
            "/agent/vision/face_id/pb_3Aaimdk_2Eprotocol_2EFaceIdResult",
            self.face_id_callback,
            qos_profile,
        )

        self.get_logger().info("已开始订阅 FaceID 数据...")

    def face_id_callback(self, msg):
        try:
            if msg.serialization_type != "pb":
                self.get_logger().warn(
                    f"收到不支持的序列化类型: {msg.serialization_type}"
                )
                return

            # 拼接 bytes
            raw_bytes = b"".join(msg.data)

            # 解析 protobuf
            face_id_result = FaceIdResult()
            face_id_result.ParseFromString(raw_bytes)

            # 日志输出
            import json
            from google.protobuf.json_format import MessageToDict
            self.get_logger().info(
                f"FaceID 结果: {json.dumps(MessageToDict(face_id_result, preserving_proto_field_name=True), ensure_ascii=False, indent=2)}")

        except Exception as e:
            self.get_logger().error(f"解析 FaceID 数据时出现错误: {e}")


def main(args=None):
    rclpy.init(args=args)
    node = FaceIdSubscriber()

    try:
        node.get_logger().info("正在监听 FaceID 数据，按 Ctrl+C 退出...")
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("退出中...")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
