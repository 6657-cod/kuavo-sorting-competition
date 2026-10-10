import json
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

OBJECTS = ['尼龙水管件', '螺丝刀', '插座模块', '膨胀螺栓', '线缆'] * 2

class VisionNode(Node):
    def __init__(self):
        super().__init__('vision_node')
        self.pub = self.create_publisher(String, '/sorting/detection', 10)
        self.sub = self.create_subscription(String, '/sorting/detect_request', self.on_request, 10)
        self.get_logger().info('模拟视觉节点就绪')

    def on_request(self, msg):
        try:
            seq = int(json.loads(msg.data)['seq'])
            if not 0 <= seq < len(OBJECTS):
                raise ValueError('seq超出范围')
            result = {'seq': seq, 'type': OBJECTS[seq], 'x': 0.30 + (seq % 5) * 0.05, 'y': 0.20, 'z': 0.05}
            self.pub.publish(String(data=json.dumps(result, ensure_ascii=False)))
            self.get_logger().info(f'模拟识别: {result}')
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            self.get_logger().error(f'无效识别请求: {exc}')

def main(args=None):
    rclpy.init(args=args)
    node = VisionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
