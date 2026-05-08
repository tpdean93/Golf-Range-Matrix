"""Config loader."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml


DEFAULTS: Dict[str, Any] = {
    "paths": {
        "raw_video_dir": "C:/golf_swings/raw",
        "annotated_video_dir": "C:/golf_swings/annotated",
        "shot_data_dir": "C:/golf_swings/shot_data",
        "analysis_dir": "C:/golf_swings/analysis",
    },
    "matching": {
        "max_time_difference_seconds": 15,
        "wait_for_video_seconds": 25,
    },
    "retention": {
        "keep_recent_swings": 5,
    },
    "camera": {
        "angle": "down_the_line",
        "fps_sample_rate": 2,
    },
    "annotation": {
        "slow_motion_factor": 0.5,
        "overlays": {
            "advanced": True,
            "pelvis_depth_line": True,
            "spine_inclination_line": True,
            "head_box": True,
            "shoulder_plane_trace": True,
            "hand_path_trace": True,
        },
    },
    "server": {
        "host": "0.0.0.0",
        "port": 8765,
        "public_base_url": "",
    },
    "obs": {
        "enabled": True,
        "host": "127.0.0.1",
        "port": 4455,
        "password": "",
        "save_replay_on_shot": True,
    },
    "mqtt": {
        "enabled": True,
        "host": "192.168.68.117",
        "port": 1883,
        "username": "",
        "password": "",
        "client_id": "golf_swing_analyzer",
        "shot_topic": "golf/shot/raw",
        "context_topic": "golf/context/current",
        "enable_topic": "golf/swing/analyzer/enabled",
        "result_prefix": "golf/swing/analysis",
        "discovery_prefix": "homeassistant",
        "device_name": "Golf Swing Analyzer",
        "device_id": "golf_swing_analyzer",
    },
    "llm": {
        "enabled": False,
        "endpoint": "http://localhost:11434/api/generate",
        "model": "trinity",
        "timeout_seconds": 60,
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
    cfg = _deep_merge(DEFAULTS, user)

    for d in cfg["paths"].values():
        Path(d).mkdir(parents=True, exist_ok=True)

    return cfg
