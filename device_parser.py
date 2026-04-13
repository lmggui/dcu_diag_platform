import io
import json
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEVICE_LIST_PATH = os.path.join(BASE_DIR, 'device_list.json')
_SUBDEVICE_PATTERN = re.compile(r'\b([0-9a-fA-F]{4}:[0-9a-fA-F]{4})\b')


def _load_device_map():
    with open(DEVICE_LIST_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return {item['sub_device_id'].lower(): item['name'] for item in data.get('devices', [])}


def extract_sub_device_ids(text):
    return sorted({match.group(1).lower() for match in _SUBDEVICE_PATTERN.finditer(text)})


def extract_sub_device_ids_from_stream(stream):
    sub_ids = set()
    for raw_line in stream:
        if isinstance(raw_line, bytes):
            line = raw_line.decode('utf-8', errors='replace')
        else:
            line = raw_line
        for match in _SUBDEVICE_PATTERN.finditer(line):
            sub_ids.add(match.group(1).lower())
    return sorted(sub_ids)


def map_devices_from_text(text):
    device_map = _load_device_map()
    sub_ids = extract_sub_device_ids(text)
    matched = [sub_id for sub_id in sub_ids if sub_id in device_map]
    if not matched:
        return []
    # 只保留第一个已知设备匹配，且已经去重
    sub_id = matched[0]
    return [{
        'sub_device_id': sub_id,
        'name': device_map[sub_id],
        'known': True
    }]


def map_devices_from_stream(stream):
    device_map = _load_device_map()
    sub_ids = extract_sub_device_ids_from_stream(stream)
    matched = [sub_id for sub_id in sub_ids if sub_id in device_map]
    if not matched:
        return []
    sub_id = matched[0]
    return [{
        'sub_device_id': sub_id,
        'name': device_map[sub_id],
        'known': True
    }]
