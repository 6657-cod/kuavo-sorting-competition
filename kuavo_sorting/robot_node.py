import json
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class RobotNode(Node):
    def __init__(self):
        super().__init__('robot_node')
        self.result_pub = self.create_publisher(String, '/sorting/robot_result', 10)
        self.sub = self.create_subscription(String, '/sorting/robot_command', self.on_command, 10)
        self.busy = False
        self.pending = None
        self.timer = self.create_timer(0.7, self.tick)
        self.get_logger().info('模拟机械臂/夹爪节点就绪（不会控制真实机器人）')

    def on_command(self, msg):
        try:
            cmd = json.loads(msg.data)
            if self.busy:
                self.get_logger().warning('机器人忙，忽略新指令')
                return
            if cmd.get('action') != 'pick_and_place':
                raise ValueError('不支持的action')
            if not isinstance(cmd.get('seq'), int) or not isinstance(cmd.get('type'), str):
                raise ValueError('缺少seq或type')
            self.pending = cmd
            self.busy = True
            self.get_logger().info(f'开始模拟抓取: {cmd["type"]} -> {cmd["bin"]}')
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            self.get_logger().error(f'无效动作指令: {exc}')

    def tick(self):
        if not self.busy:
            return
        result = {'seq': self.pending['seq'], 'success': True, 'message': '模拟抓取放置成功'}
        self.result_pub.publish(String(data=json.dumps(result, ensure_ascii=False)))
        self.get_logger().info(f'模拟动作完成: 第{result["seq"] + 1}件')
        self.pending = None
        self.busy = False

def main(args=None):
    rclpy.init(args=args)
    node = RobotNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
