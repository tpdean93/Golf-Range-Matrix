"""Config loader for the SIM control agent."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml


DEFAULTS: Dict[str, Any] = {
    "mqtt": {
        "enabled": True,
        "host": "192.168.68.117",
        "port": 1883,
        "username": "",
        "password": "",
        "client_id": "golf_sim_control_agent",
        "command_topic": "golf/sim/control/command",
        "status_topic": "golf/sim/control/status",
        "discovery_prefix": "homeassistant",
        "device_name": "Golf SIM Control",
        "device_id": "golf_sim_control",
    },
    "obs": {
        "process_name": "obs64.exe",
        "exe_path": "C:/Program Files/obs-studio/bin/64bit/obs64.exe",
        "working_dir": "C:/Program Files/obs-studio/bin/64bit",
        "restart_wait_seconds": 4,
        "swing_analyzer_scene": "Swing Analyzer",
        "websocket": {
            "host": "127.0.0.1",
            "port": 4455,
            "password": "",
            "timeout_seconds": 8,
        },
    },
    "analyzer": {
        "task_name": "Golf Swing Analyzer",
        "stop_command": "",
        "start_command": "",
        "working_dir": "C:/golf-range-matrix/tools/swing-analyzer",
    },
    "archive": {
        "enabled": False,
        "destination": "",
        "keep_last": 5,
        "filename_template": "swing_{timestamp}_{original}",
    },
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: str | os.PathLike[str]) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        user = yaml.safe_load(f) or {}
    return _deep_merge(DEFAULTS, user)
