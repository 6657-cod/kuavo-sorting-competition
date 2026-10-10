"""Simulation-only vision and action models. No robot SDK calls."""
from collections import OrderedDict
import time

from .protocol import BIN_MAP, OBJECTS, coordinates, header, identifier, integer, positive


def detect(request):
    result = header(request)
    seq = result['seq']
    result.update(type=OBJECTS[seq], x=0.30 + (seq % 5) * 0.05, y=0.20, z=0.05)
    return result


class RobotSimulation:
    def __init__(self, duration=0.7, fail_first_attempts=0, clock=time.monotonic):
        self.duration = positive(duration, 'duration')
        self.fail_first_attempts = integer(fail_first_attempts, 'fail_first_attempts')
        self.clock = clock
        self.pending = None
        self.deadline = 0.0
        self.succeeded = OrderedDict()
        self.cancelled = OrderedDict()

    @staticmethod
    def _remember(cache, key, value):
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > 128:
            cache.popitem(last=False)

    def command(self, message):
        action = message.get('action')
        run_id = identifier(message.get('run_id'), 'run_id')
        if action == 'cancel':
            self._remember(self.cancelled, run_id, True)
            if self.pending and self.pending['run_id'] == run_id:
                self.pending = None
            return None
        if action != 'pick_and_place':
            raise ValueError('不支持的模拟action')
        data = header(message)
        operation = identifier(message.get('operation_id'), 'operation_id')
        if operation != f"{run_id}:{data['seq']}":
            raise ValueError('operation_id不匹配')
        category = message.get('type')
        if not isinstance(category, str) or category not in BIN_MAP:
            raise ValueError('未知类别')
        if message.get('bin') != BIN_MAP[category]:
            raise ValueError('bin与类别不匹配')
        pose = coordinates(message.get('pose'))
        data.update(operation_id=operation, type=category, bin=message['bin'], pose=pose)
        if run_id in self.cancelled:
            return None
        if operation in self.succeeded:
            cached = self.succeeded[operation]
            if any(data[key] != cached[key] for key in ('type', 'bin', 'pose')):
                raise ValueError('同一operation_id的动作内容发生变化')
            return self._result(data, True)
        if self.pending:
            if self.pending['operation_id'] == operation:
                if any(data[key] != self.pending[key] for key in ('type', 'bin', 'pose')):
                    raise ValueError('同一operation_id的动作内容发生变化')
                # Timeout retries update correlation but do not restart the simulated action.
                self.pending['request_id'] = data['request_id']
                return None
            return self._result(data, False, '模拟动作节点忙')
        self.pending = data
        self.deadline = self.clock() + self.duration
        return None

    @staticmethod
    def _result(data, success, message=None):
        return dict(run_id=data['run_id'], request_id=data['request_id'], seq=data['seq'],
                    success=success, message=message or ('模拟动作成功' if success else '注入的模拟失败'))

    def tick(self):
        if self.pending is None or self.clock() < self.deadline:
            return None
        data = self.pending
        self.pending = None
        success = data['attempt'] >= self.fail_first_attempts
        if success:
            self._remember(self.succeeded, data['operation_id'], data)
        return self._result(data, success)
