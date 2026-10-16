#!/usr/bin/env python3

# 功能：获取机器人所有关节的位置、速度和力状态信息（除去手和头）

import json
import requests
from datetime import datetime


def create_header():
    now = datetime.utcnow()
    header = {
        "timestamp": {
            "seconds": int(now.timestamp()),
            "nanos": now.microsecond * 1000,
            "ms_since_epoch": int(now.timestamp() * 1000),
        },
        "control_source": "ControlSource_SAFE",
    }
    return header


def service_call():
    url = "http://192.168.100.100:56322/rpc/aimdk.protocol.McDataService/GetJointState"
    headers = {"Content-Type": "application/json"}
    payload = {
        "header": create_header(),
    }

    response = requests.Session().post(url, headers=headers, json=payload)
    response.raise_for_status()

    return response.json()


def pretty_print_json(json_data):
    print("Response:")
    print(json.dumps(json_data, indent=2, ensure_ascii=False))


def main():
    response = service_call()
    pretty_print_json(response)
    requests.Session().close()


if __name__ == "__main__":
    main()
