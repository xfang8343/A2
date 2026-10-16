#!/usr/bin/env python3

# 功能：输入任务id,获取任务状态

import json
import requests
from datetime import datetime
import sys


def usage():
    if len(sys.argv) != 2:
        print("Usage: python3 S_GetTaskState.py <task_num>")
        sys.exit(1)
    task_id = sys.argv[1]
    return task_id


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


def service_call(task_num):
    url = "http://192.168.100.100:56322/rpc/aimdk.protocol.McDataService/GetTaskState"
    headers = {"Content-Type": "application/json"}
    payload = {"header": create_header(), "task_id": task_num}

    response = requests.Session().post(url, headers=headers, json=payload)
    response.raise_for_status()

    return response.json()


def pretty_print_json(json_data):
    print("Response:")
    print(json.dumps(json_data, indent=2, ensure_ascii=False))


def main():
    task_id = usage()
    response = service_call(task_id)
    pretty_print_json(response)
    requests.Session().close()


if __name__ == "__main__":
    main()
