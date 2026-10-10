"""ROS transport adapter for the simulation-only sorting state machine."""
import json

from rclpy.node import Node
from std_msgs.msg import String

from .protocol import decode, identifier
from .ros_support import spin, status_qos
from .state_machine import SortingMachine


class SortingNode(Node):
    def __init__(self):
        super().__init__('sorting_node')
        timeout = self.declare_parameter('timeout_seconds', 5.0).value
        retries = self.declare_parameter('max_retries', 2).value
        self.publishers_by_event = {
            'status': self.create_publisher(String, '/sorting/status', status_qos()),
            'detect_request': self.create_publisher(String, '/sorting/detect_request', 10),
            'robot_command': self.create_publisher(String, '/sorting/robot_command', 10),
        }
        self.machine = SortingMachine(self.emit, timeout=timeout, max_retries=retries)
        self.create_subscription(String, '/sorting/control', self.on_control, 10)
        self.create_subscription(String, '/sorting/detection', self.on_detection, 10)
        self.create_subscription(String, '/sorting/robot_result', self.on_result, 10)
        self.timer = self.create_timer(0.05, self.machine.tick)
        self.machine.announce('ready', '模拟系统就绪，等待start')

    def emit(self, event, payload):
        self.publishers_by_event[event].publish(String(data=json.dumps(payload, ensure_ascii=False)))
        if event == 'status':
            self.get_logger().info(f"{payload['state']}: {payload['detail']}")

    def on_control(self, msg):
        control_id = None
        try:
            if msg.data.strip().lower() in ('start', 'stop'):
                action = msg.data.strip().lower()
            else:
                data = decode(msg.data)
                control_id = identifier(data.get('control_id'), 'control_id')
                action = data.get('action')
                if not isinstance(action, str):
                    raise ValueError('action必须为字符串')
            self.machine.control(action, control_id)
        except ValueError as exc:
            self.machine.announce('invalid', str(exc), control_id)

    def on_detection(self, msg):
        try:
            self.machine.detection_received(decode(msg.data))
        except ValueError as exc:
            self.machine.invalid_response('detection', str(exc))

    def on_result(self, msg):
        try:
            self.machine.result_received(decode(msg.data))
        except ValueError as exc:
            self.machine.invalid_response('robot_result', str(exc))


def main(args=None):
    spin(SortingNode, args)


if __name__ == '__main__':
    main()
