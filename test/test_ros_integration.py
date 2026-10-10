"""Real ROS pub/sub and launch tests; skip only when rclpy is unavailable."""
import json
import os
import signal
import subprocess
import time
import uuid

import pytest

rclpy = pytest.importorskip('rclpy', reason='ROS 2 is not installed; no ROS validation')
from rclpy.node import Node
from std_msgs.msg import String

from kuavo_sorting.protocol import BIN_MAP
from kuavo_sorting.ros_support import status_qos

pytestmark = pytest.mark.ros


class Harness:
    def __init__(self):
        self.node = Node('sorting_integration_test')
        self.statuses = []
        self.commands = []
        self.node.create_subscription(String, '/sorting/status',
                                      lambda msg: self.statuses.append(json.loads(msg.data)), status_qos())
        self.node.create_subscription(String, '/sorting/robot_command',
                                      lambda msg: self.commands.append(json.loads(msg.data)), 10)
        self.control_pub = self.node.create_publisher(String, '/sorting/control', 10)
        self.result_pub = self.node.create_publisher(String, '/sorting/robot_result', 10)

    def wait(self, condition, timeout=15.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            rclpy.spin_once(self.node, timeout_sec=0.02)
            if condition():
                return
        raise AssertionError(f'timed out; recent statuses={self.statuses[-5:]}')

    def control(self, action):
        control_id = uuid.uuid4().hex
        self.control_pub.publish(String(data=json.dumps({'action': action, 'control_id': control_id})))
        self.wait(lambda: any(s.get('control_id') == control_id for s in self.statuses))
        return next(s for s in reversed(self.statuses) if s.get('control_id') == control_id)

    def finished(self, run_id):
        self.wait(lambda: any(s['run_id'] == run_id and s['state'] in ('finished', 'error')
                             for s in self.statuses))
        final = next(s for s in reversed(self.statuses)
                     if s['run_id'] == run_id and s['state'] in ('finished', 'error'))
        assert final['state'] == 'finished', final
        assert final['completed'] == 10
        assert final['counts'] == {category: 2 for category in BIN_MAP}
        items = [s['completed'] for s in self.statuses
                 if s['run_id'] == run_id and s['state'] == 'completed_item']
        assert items == list(range(1, 11))
        return final


@pytest.fixture
def launched(request, monkeypatch, tmp_path):
    # Separate from the user's normal domain and other onboarding containers.
    monkeypatch.setenv('ROS_DOMAIN_ID', '176')
    monkeypatch.setenv('ROS_LOCALHOST_ONLY', '1')
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path / 'ros_logs'))
    parameters = {'action_seconds': '0.05', 'timeout_seconds': '1.0'}
    parameters.update(getattr(request, 'param', {}))
    command = ['ros2', 'launch', 'kuavo_sorting', 'sorting.launch.py']
    command += [f'{key}:={value}' for key, value in parameters.items()]
    log_path = tmp_path / 'launch.log'
    with log_path.open('w') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        harness = None
        try:
            rclpy.init()
            harness = Harness()
            harness.wait(lambda: any(s['state'] == 'ready' for s in harness.statuses)
                         and harness.control_pub.get_subscription_count() > 0
                         and harness.node.count_subscribers('/sorting/detect_request') > 0
                         and harness.node.count_subscribers('/sorting/robot_command') >= 2)
            yield harness
        except Exception:
            print(log_path.read_text())
            raise
        finally:
            if harness is not None:
                harness.node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()
            # Kill only our launch process group, including all three child nodes.
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)


def test_ros_normal_inventory(launched):
    start = launched.control('start')
    assert start['state'] == 'running'
    launched.finished(start['run_id'])
    assert all(s['simulated'] for s in launched.statuses)


@pytest.mark.parametrize('launched', [
    {'drop_first_attempts': '1', 'timeout_seconds': '0.25'},
    {'fail_first_attempts': '1'},
], indirect=True, ids=['detection-timeout-recovery', 'action-failure-recovery'])
def test_ros_retry_recovery(launched):
    start = launched.control('start')
    launched.finished(start['run_id'])
    retries = [s for s in launched.statuses if s['state'] == 'retrying']
    assert len(retries) == 10
    assert all(s['attempt'] == 1 for s in retries)


@pytest.mark.parametrize('launched', [
    {'drop_first_attempts': '10', 'max_retries': '1', 'timeout_seconds': '0.2'},
    {'fail_first_attempts': '10', 'max_retries': '1'},
], indirect=True, ids=['timeout-exhaustion', 'failure-exhaustion'])
def test_ros_retry_exhaustion(launched):
    start = launched.control('start')
    launched.wait(lambda: any(s['state'] == 'error' for s in launched.statuses))
    final = next(s for s in reversed(launched.statuses) if s['state'] == 'error')
    assert final['run_id'] == start['run_id'] and final['completed'] == 0
    assert final['attempt'] == 1 and '重试耗尽' in final['detail']
    if '等待超时' in final['detail']:
        assert 'wait_detection' in final['detail']


@pytest.mark.parametrize('launched', [{'action_seconds': '0.25'}], indirect=True)
def test_ros_stop_restart_and_stale_feedback(launched):
    old_run = launched.control('start')['run_id']
    launched.wait(lambda: any(c.get('action') == 'pick_and_place' for c in launched.commands))
    old = next(c for c in launched.commands if c.get('action') == 'pick_and_place')
    assert launched.control('start')['state'] == 'busy'
    assert launched.control('stop')['state'] == 'stopped'
    new_run = launched.control('start')['run_id']
    assert new_run != old_run
    # Replay an old success during the new task; it must never advance that task.
    launched.result_pub.publish(String(data=json.dumps({
        'run_id': old_run, 'request_id': old['request_id'], 'seq': old['seq'], 'success': True})))
    launched.finished(new_run)
    assert not any(s['run_id'] == old_run and s['state'] == 'finished'
                   for s in launched.statuses)


@pytest.mark.parametrize('launched', [{'action_seconds': '0.5'}], indirect=True)
def test_ros_task_client_acknowledgements_and_exit_codes(launched):
    def client(action):
        return subprocess.run(['ros2', 'run', 'kuavo_sorting', 'task_client', action],
                              capture_output=True, text=True, timeout=15)
    assert client('start').returncode == 0
    assert client('start').returncode == 1
    assert client('stop').returncode == 0
    assert client('invalid').returncode == 2


def test_ros_task_client_missing_server(monkeypatch):
    monkeypatch.setenv('ROS_DOMAIN_ID', '177')
    monkeypatch.setenv('ROS_LOCALHOST_ONLY', '1')
    process = subprocess.run(['ros2', 'run', 'kuavo_sorting', 'task_client',
                              'start', '--timeout', '0.2'],
                             capture_output=True, text=True, timeout=10)
    assert process.returncode == 1
    assert '未发现调度节点' in process.stderr + process.stdout
