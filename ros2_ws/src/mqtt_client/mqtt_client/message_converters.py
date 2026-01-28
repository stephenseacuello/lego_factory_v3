"""
Message converters for MQTT-ROS 2 bridge.
Handles serialization between ROS messages and JSON for MQTT.
"""
import json
from typing import Any, Dict

from builtin_interfaces.msg import Time


def time_to_dict(stamp: Time) -> Dict[str, int]:
    """Convert ROS Time to dictionary."""
    return {
        'sec': stamp.sec,
        'nanosec': stamp.nanosec
    }


def dict_to_time(data: Dict[str, int]) -> Time:
    """Convert dictionary to ROS Time."""
    time = Time()
    time.sec = data.get('sec', 0)
    time.nanosec = data.get('nanosec', 0)
    return time


def machine_status_to_json(msg) -> str:
    """Convert MachineStatus message to JSON string."""
    data = {
        'machine_id': msg.machine_id,
        'state': msg.state,
        'state_text': msg.state_text,
        'mpos_x': msg.mpos_x,
        'mpos_y': msg.mpos_y,
        'mpos_z': msg.mpos_z,
        'wpos_x': msg.wpos_x,
        'wpos_y': msg.wpos_y,
        'wpos_z': msg.wpos_z,
        'feed_rate': msg.feed_rate,
        'spindle_speed': msg.spindle_speed,
        'line_number': msg.line_number,
        'buffer_available': msg.buffer_available,
        'timestamp': time_to_dict(msg.timestamp)
    }
    return json.dumps(data)


def json_to_machine_status(json_str: str, msg_class):
    """Convert JSON string to MachineStatus message."""
    data = json.loads(json_str)
    msg = msg_class()
    msg.machine_id = data.get('machine_id', '')
    msg.state = data.get('state', 0)
    msg.state_text = data.get('state_text', '')
    msg.mpos_x = float(data.get('mpos_x', 0.0))
    msg.mpos_y = float(data.get('mpos_y', 0.0))
    msg.mpos_z = float(data.get('mpos_z', 0.0))
    msg.wpos_x = float(data.get('wpos_x', 0.0))
    msg.wpos_y = float(data.get('wpos_y', 0.0))
    msg.wpos_z = float(data.get('wpos_z', 0.0))
    msg.feed_rate = float(data.get('feed_rate', 0.0))
    msg.spindle_speed = float(data.get('spindle_speed', 0.0))
    msg.line_number = int(data.get('line_number', 0))
    msg.buffer_available = int(data.get('buffer_available', 0))
    if 'timestamp' in data:
        msg.timestamp = dict_to_time(data['timestamp'])
    return msg


def sensor_reading_to_json(msg) -> str:
    """Convert SensorReading message to JSON string."""
    data = {
        'sensor_id': msg.sensor_id,
        'sensor_type': msg.sensor_type,
        'value': msg.value,
        'values': list(msg.values) if msg.values else [],
        'unit': msg.unit,
        'valid': msg.valid,
        'confidence': msg.confidence,
        'timestamp': time_to_dict(msg.header.stamp)
    }
    return json.dumps(data)


def json_to_sensor_reading(json_str: str, msg_class):
    """Convert JSON string to SensorReading message."""
    data = json.loads(json_str)
    msg = msg_class()
    msg.sensor_id = data.get('sensor_id', '')
    msg.sensor_type = data.get('sensor_type', '')
    msg.value = float(data.get('value', 0.0))
    msg.values = data.get('values', [])
    msg.unit = data.get('unit', '')
    msg.valid = data.get('valid', True)
    msg.confidence = float(data.get('confidence', 1.0))
    if 'timestamp' in data:
        msg.header.stamp = dict_to_time(data['timestamp'])
    return msg


def alarm_to_json(msg) -> str:
    """Convert Alarm message to JSON string."""
    data = {
        'alarm_id': msg.alarm_id,
        'machine_id': msg.machine_id,
        'alarm_code': msg.alarm_code,
        'message': msg.message,
        'severity': msg.severity,
        'acknowledged': msg.acknowledged,
        'timestamp': time_to_dict(msg.timestamp)
    }
    return json.dumps(data)


def json_to_alarm(json_str: str, msg_class):
    """Convert JSON string to Alarm message."""
    data = json.loads(json_str)
    msg = msg_class()
    msg.alarm_id = data.get('alarm_id', '')
    msg.machine_id = data.get('machine_id', '')
    msg.alarm_code = int(data.get('alarm_code', 0))
    msg.message = data.get('message', '')
    msg.severity = int(data.get('severity', 0))
    msg.acknowledged = data.get('acknowledged', False)
    if 'timestamp' in data:
        msg.timestamp = dict_to_time(data['timestamp'])
    return msg


def grbl_status_to_json(msg) -> str:
    """Convert GrblStatus message to JSON string."""
    data = {
        'machine_id': msg.machine_id,
        'state': msg.state,
        'state_code': msg.state_code,
        'pos_x': msg.pos_x,
        'pos_y': msg.pos_y,
        'pos_z': msg.pos_z,
        'feed_rate': msg.feed_rate,
        'spindle_speed': msg.spindle_speed,
        'line_number': msg.line_number,
        'feed_override': msg.feed_override,
        'spindle_override': msg.spindle_override,
        'timestamp': time_to_dict(msg.header.stamp)
    }
    return json.dumps(data)


def json_to_grbl_status(json_str: str, msg_class):
    """Convert JSON string to GrblStatus message."""
    data = json.loads(json_str)
    msg = msg_class()
    msg.machine_id = data.get('machine_id', '')
    msg.state = data.get('state', '')
    msg.state_code = int(data.get('state_code', 0))
    msg.pos_x = float(data.get('pos_x', 0.0))
    msg.pos_y = float(data.get('pos_y', 0.0))
    msg.pos_z = float(data.get('pos_z', 0.0))
    msg.feed_rate = float(data.get('feed_rate', 0.0))
    msg.spindle_speed = float(data.get('spindle_speed', 0.0))
    msg.line_number = int(data.get('line_number', 0))
    msg.feed_override = int(data.get('feed_override', 100))
    msg.spindle_override = int(data.get('spindle_override', 100))
    if 'timestamp' in data:
        msg.header.stamp = dict_to_time(data['timestamp'])
    return msg


def generic_to_json(data: Any) -> str:
    """Convert generic data to JSON string."""
    return json.dumps(data)


def json_to_dict(json_str: str) -> Dict:
    """Convert JSON string to dictionary."""
    return json.loads(json_str)
