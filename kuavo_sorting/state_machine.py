"""Deterministic state machine; no ROS import, hardware or wall-clock sleeps."""
import time
import uuid

from .protocol import BIN_MAP, TOTAL, coordinates, integer, positive


class SortingMachine:
    def __init__(self, emit, timeout=5.0, max_retries=2, clock=time.monotonic):
        self.emit = emit
        self.timeout = positive(timeout, 'timeout')
        self.max_retries = integer(max_retries, 'max_retries')
        self.clock = clock
        self.active = False
        self.phase = 'idle'
        self.run_id = ''
        self.request_id = ''
        self.completed = 0
        self.counts = {category: 0 for category in BIN_MAP}
        self.attempt = 0
        self.deadline = 0.0
        self.detection = None

    def announce(self, state, detail, control_id=None):
        message = dict(state=state, phase=self.phase, run_id=self.run_id,
                       completed=self.completed, total=TOTAL, counts=dict(self.counts),
                       attempt=self.attempt, detail=detail, simulated=True)
        if control_id is not None:
            message['control_id'] = control_id
        self.emit('status', message)

    def control(self, action, control_id=None):
        if action == 'start':
            if self.active:
                self.announce('busy', '任务正在运行，忽略重复start', control_id)
                return
            self.run_id = uuid.uuid4().hex
            self.completed = 0
            self.counts = {category: 0 for category in BIN_MAP}
            self.active = True
            self.phase = 'wait_detection'
            self.attempt = 0
            self.detection = None
            self.announce('running', '开始10件模拟分拣', control_id)
            self._request()
        elif action == 'stop':
            self._cancel()
            self.active = False
            self.phase = 'stopped'
            self.request_id = ''
            self.announce('stopped', '模拟任务停止；这不是实体机器人急停', control_id)
        else:
            self.announce('invalid', f'未知指令: {action}', control_id)

    def _cancel(self):
        if self.active:
            self.emit('robot_command', {'action': 'cancel', 'run_id': self.run_id})

    def _request(self):
        self.request_id = uuid.uuid4().hex
        self.deadline = self.clock() + self.timeout
        message = dict(run_id=self.run_id, request_id=self.request_id,
                       seq=self.completed, attempt=self.attempt)
        if self.phase == 'wait_detection':
            self.emit('detect_request', message)
            self.announce('detecting', f'请求识别第{self.completed + 1}件')
        else:
            message.update(action='pick_and_place', operation_id=f'{self.run_id}:{self.completed}',
                           type=self.detection['type'], bin=BIN_MAP[self.detection['type']],
                           pose=self.detection['pose'])
            self.emit('robot_command', message)
            self.announce('moving', f"模拟动作: {message['type']} -> {message['bin']}")

    def _retry(self, reason):
        waiting_phase = self.phase
        if self.attempt < self.max_retries:
            self.attempt += 1
            self.announce('retrying', f'{waiting_phase}: {reason}; 重试{self.attempt}/{self.max_retries}')
            self._request()
        else:
            self._cancel()
            self.active = False
            self.phase = 'error'
            self.request_id = ''
            self.announce('error', f'第{self.completed + 1}件{waiting_phase}: {reason}; 重试耗尽')

    def tick(self):
        if self.active and self.clock() >= self.deadline:
            self._retry('等待超时')

    def invalid_response(self, source, reason):
        expected = 'detection' if self.phase == 'wait_detection' else 'robot_result'
        if self.active and source == expected:
            self._retry(f'消息无效: {reason}')

    def _matches(self, message, phase):
        return (self.active and self.phase == phase and isinstance(message, dict)
                and message.get('run_id') == self.run_id
                and message.get('request_id') == self.request_id)

    def detection_received(self, message):
        if not self._matches(message, 'wait_detection'):
            return
        try:
            if integer(message.get('seq'), 'seq') != self.completed:
                raise ValueError('seq不匹配')
            category = message.get('type')
            if not isinstance(category, str) or category not in BIN_MAP:
                raise ValueError('未知零件类别')
            if self.counts[category] >= 2:
                raise ValueError(f'{category}已完成两件')
            pose = coordinates([message.get(axis) for axis in ('x', 'y', 'z')])
        except ValueError as exc:
            self._retry(str(exc))
            return
        self.detection = {'type': category, 'pose': pose}
        self.phase = 'wait_robot'
        self.attempt = 0
        self._request()

    def result_received(self, message):
        if not self._matches(message, 'wait_robot'):
            return
        try:
            if integer(message.get('seq'), 'seq') != self.completed:
                raise ValueError('seq不匹配')
            if type(message.get('success')) is not bool:
                raise ValueError('success必须为布尔值')
            if not message['success']:
                raise ValueError(str(message.get('message', '模拟动作失败')))
        except ValueError as exc:
            self._retry(str(exc))
            return
        self.completed += 1
        self.counts[self.detection['type']] += 1
        self.announce('completed_item', f'第{self.completed}件模拟分拣完成')
        self.attempt = 0
        if self.completed == TOTAL:
            self.active = False
            self.phase = 'finished'
            self.request_id = ''
            self.announce('finished', '五类各两件，共10件模拟分拣完成')
        else:
            self.phase = 'wait_detection'
            self._request()
