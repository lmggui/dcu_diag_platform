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


def map_devices_from_text(text):
    device_map = _load_device_map()
    sub_ids = extract_sub_device_ids(text)
    result = []
    for sub_id in sub_ids:
        device_name = device_map.get(sub_id)
        result.append({
            'sub_device_id': sub_id,
            'name': device_name if device_name else '未知设备',
            'known': sub_id in device_map
        })
    return result
