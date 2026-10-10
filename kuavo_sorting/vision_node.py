"""Deterministic simulated vision; does not consume camera data."""
import json

from rclpy.node import Node
from std_msgs.msg import String

from .protocol import decode, integer
from .ros_support import spin
from .simulation import detect


class VisionNode(Node):
    def __init__(self):
        super().__init__('vision_node')
        self.drop_first_attempts = integer(
            self.declare_parameter('drop_first_attempts', 0).value, 'drop_first_attempts')
        self.pub = self.create_publisher(String, '/sorting/detection', 10)
        self.sub = self.create_subscription(String, '/sorting/detect_request', self.on_request, 10)
        self.get_logger().info('模拟视觉就绪；无真实相机输入')

    def on_request(self, msg):
        try:
            result = detect(decode(msg.data))
            if result['attempt'] < self.drop_first_attempts:
                self.get_logger().info('故障注入：丢弃本次模拟识别响应')
                return
            self.pub.publish(String(data=json.dumps(result, ensure_ascii=False)))
        except ValueError as exc:
            self.get_logger().error(f'无效模拟识别请求: {exc}')


def main(args=None):
    spin(VisionNode, args)


if __name__ == '__main__':
    main()
