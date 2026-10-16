#!/usr/bin/env python3
import time

import requests
from retry_decorator import retry


@retry(max_attempts=1, delay=1.0)
def set_action(action_name: str, mc_ip: str = "192.168.100.100"):
    url = f"http://{mc_ip}:56322/rpc/aimdk.protocol.McActionService/SetAction"
    headers = {"Content-Type": "application/json"}
    payload = {
        "command": {"action": "McAction_USE_EXT_CMD", "ext_action": action_name},
    }
    rsp = requests.post(url, headers=headers, json=payload, timeout=1.0)
    rsp.raise_for_status()
    return rsp


@retry(max_attempts=1, delay=1.0)
def get_action(mc_ip: str = "192.168.100.100"):
    url = f"http://{mc_ip}:56322/rpc/aimdk.protocol.McActionService/GetAction"
    headers = {"Content-Type": "application/json"}
    rsp = requests.post(url, headers=headers, json={}, timeout=1.0)
    rsp.raise_for_status()
    return rsp.json()["info"]["current_action"]


def ensure_action(
    action_name: str, retries=3, retry_interval=1.0, mc_ip: str = "192.168.100.100"
):
    try:
        for i in range(retries):
            if get_action(mc_ip) == action_name:
                return True
            set_action(action_name, mc_ip)
            time.sleep(0.1 if i == 0 else retry_interval)
    except Exception as e:
        print(f"Failed to set action: {e}")
        return False
    return False


if __name__ == "__main__":
    print(f"Current action: {get_action(mc_ip='192.168.100.100')}")
