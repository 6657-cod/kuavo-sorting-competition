"""Send a correlated command and require an acknowledgement; useful exit codes."""
import argparse
import json
import time
import uuid

import rclpy
from rclpy.node import Node
from rclpy.utilities import remove_ros_args
from std_msgs.msg import String

from .protocol import decode, positive
from .ros_support import status_qos


def main(args=None):
    parser = argparse.ArgumentParser(description='模拟分拣任务控制')
    parser.add_argument('action', choices=('start', 'stop'), nargs='?', default='start')
    parser.add_argument('--timeout', type=float, default=5.0, help='发现与确认分别等待的秒数')
    options = parser.parse_args(remove_ros_args(args=args)[1:])
    try:
        positive(options.timeout, 'timeout')
    except ValueError as exc:
        parser.error(str(exc))
    rclpy.init(args=args)
    node = Node('task_client')
    control_id = uuid.uuid4().hex
    acknowledgements = []

    def on_status(msg):
        try:
            data = decode(msg.data)
        except ValueError:
            return
        if data.get('control_id') == control_id:
            acknowledgements.append(data)

    node.create_subscription(String, '/sorting/status', on_status, status_qos())
    pub = node.create_publisher(String, '/sorting/control', 10)
    exit_code = 1
    try:
        deadline = time.monotonic() + options.timeout
        while time.monotonic() < deadline:
            if pub.get_subscription_count() > 0 and node.count_publishers('/sorting/status') > 0:
                break
            rclpy.spin_once(node, timeout_sec=0.05)
        else:
            node.get_logger().error('未发现调度节点；请先启动launch')
            raise SystemExit(1)
        pub.publish(String(data=json.dumps({'action': options.action, 'control_id': control_id})))
        deadline = time.monotonic() + options.timeout
        while not acknowledgements and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)
        if not acknowledgements:
            node.get_logger().error('指令确认超时')
        else:
            state = acknowledgements[-1].get('state')
            expected = 'running' if options.action == 'start' else 'stopped'
            if state == expected:
                node.get_logger().info(f'调度节点已确认: {options.action}')
                exit_code = 0
            else:
                node.get_logger().error(f'指令未被接受: {state}')
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    raise SystemExit(exit_code)


if __name__ == '__main__':
    main()
