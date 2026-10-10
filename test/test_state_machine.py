import copy

import pytest

from kuavo_sorting.protocol import BIN_MAP, OBJECTS, decode
from kuavo_sorting.simulation import RobotSimulation, detect
from kuavo_sorting.state_machine import SortingMachine


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds=1.0):
        self.now += seconds


@pytest.fixture
def rig():
    clock = Clock()
    events = []
    machine = SortingMachine(lambda kind, data: events.append((kind, data)),
                             timeout=1.0, max_retries=2, clock=clock)
    return machine, clock, events


def last(events, kind):
    return next(data for event, data in reversed(events) if event == kind)


def move(machine, events):
    machine.detection_received(detect(last(events, 'detect_request')))
    return last(events, 'robot_command')


def result(command, success=True):
    return {key: command[key] for key in ('run_id', 'request_id', 'seq')} | {'success': success}


def test_full_inventory(rig):
    machine, _, events = rig
    machine.control('start', 'start-1')
    categories = []
    for seq in range(10):
        command = move(machine, events)
        assert command['seq'] == seq
        assert command['bin'] == BIN_MAP[command['type']]
        categories.append(command['type'])
        machine.result_received(result(command))
        # Duplicates cannot increment completion twice.
        machine.result_received(result(command))
    assert categories == list(OBJECTS)
    assert machine.completed == 10 and not machine.active
    assert machine.counts == {category: 2 for category in BIN_MAP}
    assert last(events, 'status')['state'] == 'finished'
    assert [data['completed'] for kind, data in events
            if kind == 'status' and data['state'] == 'completed_item'] == list(range(1, 11))


def test_duplicate_start_and_unknown_control(rig):
    machine, _, events = rig
    machine.control('start')
    run_id, request_id = machine.run_id, machine.request_id
    machine.control('start', 'duplicate')
    assert last(events, 'status')['state'] == 'busy'
    assert last(events, 'status')['control_id'] == 'duplicate'
    machine.control('invalid')
    assert last(events, 'status')['state'] == 'invalid'
    assert (machine.run_id, machine.request_id) == (run_id, request_id)


@pytest.mark.parametrize('phase', ['wait_detection', 'wait_robot'])
def test_timeout_retries_and_reports_original_phase(rig, phase):
    machine, clock, events = rig
    machine.control('start')
    if phase == 'wait_robot':
        move(machine, events)
    ids = {machine.request_id}
    for attempt in (1, 2):
        clock.advance()
        machine.tick()
        assert machine.attempt == attempt and machine.active
        assert machine.request_id not in ids
        ids.add(machine.request_id)
    clock.advance()
    machine.tick()
    status = last(events, 'status')
    assert status['state'] == 'error' and phase in status['detail']
    assert status['completed'] == 0 and not machine.active
    assert last(events, 'robot_command')['action'] == 'cancel'


def test_failed_action_retries_same_operation(rig):
    machine, _, events = rig
    machine.control('start')
    old = move(machine, events)
    machine.result_received(result(old, False))
    new = last(events, 'robot_command')
    assert new['operation_id'] == old['operation_id']
    assert new['request_id'] != old['request_id'] and new['attempt'] == 1
    machine.result_received(result(old))
    assert machine.completed == 0
    machine.result_received(result(new))
    assert machine.completed == 1 and machine.attempt == 0


def test_stop_restart_rejects_old_and_out_of_order_feedback(rig):
    machine, _, events = rig
    machine.control('start')
    old = move(machine, events)
    machine.control('stop', 'stop-1')
    assert last(events, 'robot_command') == {'action': 'cancel', 'run_id': old['run_id']}
    machine.result_received(result(old))
    assert machine.completed == 0 and machine.phase == 'stopped'
    machine.control('start')
    assert machine.run_id != old['run_id']
    machine.result_received(result(old))
    machine.detection_received(detect(old))
    assert machine.phase == 'wait_detection' and machine.completed == 0
    new = move(machine, events)
    machine.result_received(result(old))
    assert machine.completed == 0
    machine.result_received(result(new))
    assert machine.completed == 1


@pytest.mark.parametrize('patch', [
    {'type': 'unknown'}, {'type': []}, {'x': '0.2'}, {'y': float('nan')},
    {'z': float('inf')}, {'x': True}, {'seq': True}, {'seq': -1}, {'seq': 9},
])
def test_invalid_detection_is_retried(rig, patch):
    machine, _, events = rig
    machine.control('start')
    data = detect(last(events, 'detect_request'))
    data.update(patch)
    machine.detection_received(data)
    assert machine.attempt == 1 and machine.completed == 0
    assert machine.phase == 'wait_detection'


@pytest.mark.parametrize('success', [None, 1, 'true', [], False])
def test_invalid_or_failed_result_is_retried(rig, success):
    machine, _, events = rig
    machine.control('start')
    data = result(move(machine, events))
    data['success'] = success
    machine.result_received(data)
    assert machine.attempt == 1 and machine.completed == 0


def test_third_item_of_same_category_is_rejected(rig):
    machine, _, events = rig
    machine.control('start')
    for _ in range(2):
        data = detect(last(events, 'detect_request'))
        data['type'] = OBJECTS[0]
        machine.detection_received(data)
        machine.result_received(result(last(events, 'robot_command')))
    data = detect(last(events, 'detect_request'))
    data['type'] = OBJECTS[0]
    machine.detection_received(data)
    assert machine.attempt == 1 and machine.completed == 2


def test_malformed_messages_and_irrelevant_sources(rig):
    machine, _, events = rig
    machine.control('start')
    machine.invalid_response('robot_result', 'bad json')
    machine.result_received([])
    machine.detection_received({})
    assert machine.attempt == 0
    machine.invalid_response('detection', 'bad json')
    assert machine.attempt == 1
    machine.control('stop')
    machine.invalid_response('detection', 'bad json')
    assert machine.phase == 'stopped'


@pytest.mark.parametrize('raw', ['[]', 'null', 'true', '1', '"start"', '{'])
def test_json_requires_object(raw):
    with pytest.raises(ValueError):
        decode(raw)


@pytest.mark.parametrize('seq', [True, -1, 10, '0', 0.5, None])
def test_vision_strict_sequence(seq):
    with pytest.raises(ValueError):
        detect(dict(run_id='r', request_id='q', seq=seq, attempt=0))


@pytest.mark.parametrize('kwargs', [{'timeout': 0}, {'timeout': float('nan')},
                                  {'max_retries': -1}, {'max_retries': True}])
def test_bad_machine_configuration(kwargs):
    with pytest.raises(ValueError):
        SortingMachine(lambda *_: None, **kwargs)


def test_zero_retries_fails_immediately():
    clock = Clock()
    machine = SortingMachine(lambda *_: None, timeout=1.0, max_retries=0, clock=clock)
    machine.control('start')
    clock.advance()
    machine.tick()
    assert machine.phase == 'error' and machine.attempt == 0


def test_robot_cancel_and_duplicate_actions(rig):
    machine, clock, events = rig
    robot = RobotSimulation(duration=0.5, clock=clock)
    machine.control('start')
    command = move(machine, events)
    assert robot.command(command) is None
    clock.advance(0.2)
    retry = dict(command, request_id='retry', attempt=1)
    assert robot.command(retry) is None
    clock.advance(0.3)
    feedback = robot.tick()
    assert feedback['request_id'] == 'retry' and feedback['success']
    # A lost success reply is replayed without scheduling another action.
    replay = robot.command(dict(retry, request_id='replay'))
    assert replay['success'] and robot.pending is None
    robot.command({'action': 'cancel', 'run_id': command['run_id']})
    assert robot.command(command) is None


def test_robot_pending_cancel_and_failure_injection(rig):
    machine, clock, events = rig
    robot = RobotSimulation(duration=0.5, fail_first_attempts=1, clock=clock)
    machine.control('start')
    command = move(machine, events)
    robot.command(command)
    clock.advance(0.5)
    assert robot.tick()['success'] is False
    robot.command(dict(command, attempt=1, request_id='retry'))
    robot.command({'action': 'cancel', 'run_id': command['run_id']})
    clock.advance()
    assert robot.tick() is None and robot.pending is None


@pytest.mark.parametrize('patch', [{'bin': 'Z'}, {'pose': [0, 0]}, {'type': []},
                                  {'operation_id': 'wrong'}, {'action': 'sdk_grasp'}])
def test_invalid_robot_command_has_no_side_effect(rig, patch):
    machine, clock, events = rig
    robot = RobotSimulation(clock=clock)
    machine.control('start')
    command = copy.deepcopy(move(machine, events))
    command.update(patch)
    with pytest.raises(ValueError):
        robot.command(command)
    assert robot.pending is None


def test_changed_operation_content_is_rejected(rig):
    machine, clock, events = rig
    robot = RobotSimulation(clock=clock)
    machine.control('start')
    command = move(machine, events)
    robot.command(command)
    with pytest.raises(ValueError):
        robot.command(dict(command, pose=[9.0, 9.0, 9.0]))
    clock.advance()
    assert robot.tick()['success']
    with pytest.raises(ValueError):
        robot.command(dict(command, pose=[9.0, 9.0, 9.0]))


def test_robot_busy_does_not_overwrite_pending(rig):
    machine, clock, events = rig
    robot = RobotSimulation(clock=clock)
    machine.control('start')
    command = move(machine, events)
    robot.command(command)
    other = dict(command, seq=1, operation_id=f"{command['run_id']}:1")
    assert robot.command(other)['success'] is False
    clock.advance()
    assert robot.tick()['seq'] == 0
