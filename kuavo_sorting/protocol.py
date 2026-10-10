"""Internal JSON protocol for the simulated demo, not a Kuavo SDK."""
import json
import math

BIN_MAP = {'尼龙水管件': 'A', '螺丝刀': 'B', '插座模块': 'C', '膨胀螺栓': 'D', '线缆': 'E'}
OBJECTS = tuple(BIN_MAP) * 2
TOTAL = len(OBJECTS)


def decode(text):
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError('消息必须为JSON对象')
    return value


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f'{name}必须为不小于{minimum}的整数')
    return value


def identifier(value, name):
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ValueError(f'{name}必须为1..128字符的字符串')
    return value


def header(message):
    identifier(message.get('run_id'), 'run_id')
    identifier(message.get('request_id'), 'request_id')
    seq = integer(message.get('seq'), 'seq')
    if seq >= TOTAL:
        raise ValueError('seq超出0..9范围')
    integer(message.get('attempt'), 'attempt')
    return {key: message[key] for key in ('run_id', 'request_id', 'seq', 'attempt')}


def coordinates(values):
    if not isinstance(values, (list, tuple)) or len(values) != 3:
        raise ValueError('pose必须包含三个坐标')
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
        raise ValueError('坐标必须为有限数值')
    return list(values)


def positive(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f'{name}必须为正的有限数值')
    return float(value)
