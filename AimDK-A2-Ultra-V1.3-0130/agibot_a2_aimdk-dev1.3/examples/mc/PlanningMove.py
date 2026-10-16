#! /usr/bin/env python3
import json
import requests
from datetime import datetime


def create_header():
    now = datetime.now()
    header = {
        "timestamp": {
            "seconds": int(now.timestamp()),
            "nanos": now.microsecond * 1000,
            "ms_since_epoch": int(now.timestamp() * 1000),
        },
        "control_source": "ControlSource_MANUAL",
    }
    return header


def send_json_data(json_data, url):
    json_str = json.dumps(json_data, indent=2)
    print("Sending JSON data:")
    print(json_str)
    print("")

    headers = {"content-type": "application/json"}
    response = requests.post(url, headers=headers, data=json_str)

    print(f"Response: {response.status_code}")
    print(response.text)
    print("")


def main():
    url = "http://192.168.100.100:56322/rpc/aimdk.protocol.McMotionService/PlanningMove"
    leftTrl = [0.35, 0.35, 0.25]
    leftQuat = [0.818758, 0.570822, -0.0606913, -0.0106989]
    rightTrl = [0.35, -0.35, 0.25]
    rightQuat = [0.818761, -0.570817, -0.0606912, 0.0106992]
    data = {
        "header": create_header(),
        "group": "McPlanningGroup_LEFT_ARM",
        "mode": "McPlanningMode_DEFAULT",
        "target": {
            "type": "SE3",
            "left": {
                "position": {"x": leftTrl[0], "y": leftTrl[1], "z": leftTrl[2]},
                "orientation": {
                    "x": leftQuat[1],
                    "y": leftQuat[2],
                    "z": leftQuat[3],
                    "w": leftQuat[0],
                },
            },
            "right": {
                "position": {"x": rightTrl[0], "y": rightTrl[1], "z": rightTrl[2]},
                "orientation": {
                    "x": rightQuat[1],
                    "y": rightQuat[2],
                    "z": rightQuat[3],
                    "w": rightQuat[0],
                },
            },
        },
        "reference": {"joint_position": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]},
    }
    send_json_data(data, url)


if __name__ == "__main__":
    main()
