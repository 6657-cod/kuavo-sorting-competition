import sys
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


def main(args=None):
    rclpy.init(args=args)
    node = Node('task_client')
    pub = node.create_publisher(String, '/sorting/control', 10)
    action = sys.argv[1] if len(sys.argv) > 1 else 'start'
    if action not in ('start', 'stop'):
        node.get_logger().error('用法: ros2 run kuavo_sorting task_client start|stop')
    else:
        # 允许ROS发现订阅者，最多等5秒
        for _ in range(50):
            if pub.get_subscription_count() > 0:
                break
            rclpy.spin_once(node, timeout_sec=0.1)
        if pub.get_subscription_count() == 0:
            node.get_logger().error('未发现 /sorting/control 订阅者，先启动launch')
        else:
            pub.publish(String(data=action))
            node.get_logger().info(f'已发送: {action}')
            rclpy.spin_once(node, timeout_sec=0.2)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
