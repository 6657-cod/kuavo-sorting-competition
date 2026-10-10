"""Simulated action node, not a Kuavo hardware driver or emergency stop."""
import json

from rclpy.node import Node
from std_msgs.msg import String

from .protocol import decode
from .ros_support import spin
from .simulation import RobotSimulation


class RobotNode(Node):
    def __init__(self):
        super().__init__('robot_node')
        duration = self.declare_parameter('action_seconds', 0.7).value
        failures = self.declare_parameter('fail_first_attempts', 0).value
        self.simulation = RobotSimulation(duration=duration, fail_first_attempts=failures)
        self.result_pub = self.create_publisher(String, '/sorting/robot_result', 10)
        self.sub = self.create_subscription(String, '/sorting/robot_command', self.on_command, 10)
        self.timer = self.create_timer(0.05, self.tick)
        self.get_logger().info('模拟动作节点就绪；不会控制真实机器人')

    def publish(self, result):
        if result is not None:
            self.result_pub.publish(String(data=json.dumps(result, ensure_ascii=False)))

    def on_command(self, msg):
        try:
            self.publish(self.simulation.command(decode(msg.data)))
        except ValueError as exc:
            self.get_logger().error(f'无效模拟动作指令: {exc}')

    def tick(self):
        self.publish(self.simulation.tick())


def main(args=None):
    spin(RobotNode, args)


if __name__ == '__main__':
    main()
