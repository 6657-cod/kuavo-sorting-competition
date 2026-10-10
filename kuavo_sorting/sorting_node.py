import json
import time
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

BIN_MAP = {'尼龙水管件': 'A', '螺丝刀': 'B', '插座模块': 'C', '膨胀螺栓': 'D', '线缆': 'E'}
TOTAL = 10
TIMEOUT_SECONDS = 5.0

class SortingNode(Node):
    def __init__(self):
        super().__init__('sorting_node')
        self.pub_status = self.create_publisher(String, '/sorting/status', 10)
        self.pub_detect = self.create_publisher(String, '/sorting/detect_request', 10)
        self.pub_robot = self.create_publisher(String, '/sorting/robot_command', 10)
        self.create_subscription(String, '/sorting/control', self.on_control, 10)
        self.create_subscription(String, '/sorting/detection', self.on_detection, 10)
        self.create_subscription(String, '/sorting/robot_result', self.on_result, 10)
        self.timer = self.create_timer(0.2, self.tick)
        self.active = False
        self.seq = 0
        self.phase = 'idle'
        self.deadline = 0.0
        self.announce('ready', '系统就绪，请发送start指令')

    def announce(self, state, detail):
        payload = {'state': state, 'completed': self.seq, 'total': TOTAL, 'detail': detail}
        self.pub_status.publish(String(data=json.dumps(payload, ensure_ascii=False)))
        self.get_logger().info(f'{state}: {detail}')

    def on_control(self, msg):
        command = msg.data.strip().lower()
        if command == 'start':
            if self.active:
                self.announce('busy', '正在运行，忽略重复start')
                return
            self.seq = 0
            self.active = True
            self.phase = 'request_detection'
            self.announce('running', '开始新一轮10件零件分拣')
        elif command == 'stop':
            self.active = False
            self.phase = 'idle'
            self.announce('stopped', '任务停止（模拟机器人动作不支持中途急停）')
        else:
            self.announce('invalid', f'未知控制指令: {command}')

    def tick(self):
        if not self.active:
            return
        if self.phase == 'request_detection':
            self.pub_detect.publish(String(data=json.dumps({'seq': self.seq})))
            self.phase = 'wait_detection'
            self.deadline = time.monotonic() + TIMEOUT_SECONDS
            self.announce('detecting', f'请求识别第{self.seq + 1}件')
        elif self.phase in ('wait_detection', 'wait_robot') and time.monotonic() > self.deadline:
            self.active = False
            self.phase = 'idle'
            self.announce('error', f'第{self.seq + 1}件等待{self.phase}超时，请检查节点')

    def on_detection(self, msg):
        if not self.active or self.phase != 'wait_detection':
            return
        try:
            det = json.loads(msg.data)
            if det['seq'] != self.seq:
                return
            category = det['type']
            if category not in BIN_MAP:
                raise ValueError(f'未知类别: {category}')
            cmd = {'seq': self.seq, 'action': 'pick_and_place', 'type': category,
                   'bin': BIN_MAP[category], 'pose': [det['x'], det['y'], det['z']]}
            self.pub_robot.publish(String(data=json.dumps(cmd, ensure_ascii=False)))
            self.phase = 'wait_robot'
            self.deadline = time.monotonic() + TIMEOUT_SECONDS
            self.announce('moving', f'{category} -> 收纳位置{BIN_MAP[category]}')
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            self.active = False
            self.phase = 'idle'
            self.announce('error', f'识别数据无效: {exc}')

    def on_result(self, msg):
        if not self.active or self.phase != 'wait_robot':
            return
        try:
            result = json.loads(msg.data)
            if result['seq'] != self.seq:
                return
            if result.get('success') is not True:
                raise ValueError(result.get('message', '动作失败'))
            self.seq += 1
            self.announce('completed_item', f'第{self.seq}件完成')
            if self.seq == TOTAL:
                self.active = False
                self.phase = 'idle'
                self.announce('finished', '10件模拟分类完成')
            else:
                self.phase = 'request_detection'
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            self.active = False
            self.phase = 'idle'
            self.announce('error', f'动作反馈无效: {exc}')

def main(args=None):
    rclpy.init(args=args)
    node = SortingNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
