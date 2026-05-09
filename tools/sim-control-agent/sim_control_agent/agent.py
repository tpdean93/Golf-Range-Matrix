"""MQTT-controlled SIM PC helper for OBS and Swing Analyzer recovery."""
from __future__ import annotations

import json
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .config import load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("sim_control_agent")


CommandHandler = Callable[[], Dict[str, Any]]


def _no_window_flags() -> int:
    if os.name != "nt":
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _acquire_single_instance() -> socket.socket:
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", 47531))
        lock.listen(1)
        return lock
    except OSError as e:
        lock.close()
        raise RuntimeError("SIM Control Agent is already running") from e


class SimControlAgent:
    def __init__(self, cfg: Dict[str, Any]) -> None:
        self.cfg = cfg
        self.mqtt_cfg = cfg.get("mqtt", {})
        self.obs_cfg = cfg.get("obs", {})
        self.analyzer_cfg = cfg.get("analyzer", {})
        self._client = None
        self._lock = threading.Lock()
        self._last_status: Dict[str, Any] = {
            "ok": True,
            "last_command": None,
            "last_result": "starting",
            "obs_running": self._is_process_running(),
            "obs_scene": None,
            "scene_matches": None,
            "timestamp": self._now(),
        }
        self.handlers: Dict[str, CommandHandler] = {
            "restart_obs": self.restart_obs,
            "start_obs": self.start_obs,
            "select_swing_analyzer_scene": self.select_swing_analyzer_scene,
            "start_replay_buffer": self.start_replay_buffer,
            "save_replay_buffer": self.save_replay_buffer,
            "restart_analyzer": self.restart_analyzer,
        }

    def start(self) -> None:
        if not self.mqtt_cfg.get("enabled"):
            log.info("MQTT disabled in config")
            return
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            log.error("paho-mqtt not installed; pip install -r requirements.txt")
            return

        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.mqtt_cfg.get("client_id", "golf_sim_control_agent"),
        )
        if self.mqtt_cfg.get("username"):
            client.username_pw_set(
                self.mqtt_cfg["username"],
                self.mqtt_cfg.get("password") or "",
            )

        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.will_set(self._availability_topic(), "offline", retain=True)
        client.connect(
            self.mqtt_cfg["host"],
            int(self.mqtt_cfg.get("port", 1883)),
            keepalive=30,
        )
        self._client = client
        client.loop_start()
        log.info(
            "SIM control agent connecting to MQTT %s:%s",
            self.mqtt_cfg["host"],
            self.mqtt_cfg.get("port", 1883),
        )

    def stop(self) -> None:
        if self._client is None:
            return
        try:
            self._client.publish(self._availability_topic(), "offline", retain=True)
            self._client.loop_stop()
            self._client.disconnect()
        except Exception:
            pass
        self._client = None

    def loop_forever(self) -> None:
        while True:
            time.sleep(1)
            if int(time.time()) % 30 == 0:
                self.publish_status()

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code != 0:
            log.warning("MQTT connect refused: rc=%s", reason_code)
            return
        command_topic = self.mqtt_cfg["command_topic"]
        client.subscribe(command_topic)
        client.publish(self._availability_topic(), "online", retain=True)
        self._publish_discovery()
        self.publish_status()
        log.info("MQTT subscribed to command=%s", command_topic)

    def _on_message(self, client, userdata, msg) -> None:
        try:
            payload = msg.payload.decode("utf-8", errors="replace").strip()
        except Exception:
            return
        command = self._command_from_payload(payload)
        if not command:
            self._record_status(False, None, f"invalid command payload: {payload[:80]}")
            return

        handler = self.handlers.get(command)
        if handler is None:
            self._record_status(False, command, "unsupported command")
            return

        log.info("Command received: %s", command)
        try:
            result = handler()
            ok = bool(result.pop("ok", True))
            message = str(result.pop("message", "done"))
            self._record_status(ok, command, message, result)
        except Exception as e:
            log.exception("Command failed: %s", command)
            self._record_status(False, command, str(e))

    def _command_from_payload(self, payload: str) -> Optional[str]:
        if not payload:
            return None
        if payload.startswith("{"):
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                return None
            if isinstance(data, dict):
                command = data.get("command")
                return str(command).strip() if command else None
            return None
        return payload.strip()

    def _availability_topic(self) -> str:
        status_topic = self.mqtt_cfg.get("status_topic", "golf/sim/control/status")
        return status_topic.rsplit("/", 1)[0] + "/availability"

    def publish_status(self) -> None:
        if self._client is None:
            return
        with self._lock:
            payload = dict(self._last_status)
            obs_running = self._is_process_running()
            payload["obs_running"] = obs_running
            scene = self._get_obs_scene(obs_running=obs_running)
            payload["obs_scene"] = scene
            payload["scene_matches"] = self._scene_matches(scene)
            payload["timestamp"] = self._now()
            self._last_status = payload
        self._client.publish(
            self.mqtt_cfg["status_topic"],
            json.dumps(payload),
            retain=True,
        )

    def _record_status(
        self,
        ok: bool,
        command: Optional[str],
        message: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        status = {
            "ok": ok,
            "last_command": command,
            "last_result": message,
            "obs_running": self._is_process_running(),
            "timestamp": self._now(),
        }
        status["obs_scene"] = self._get_obs_scene(obs_running=bool(status["obs_running"]))
        status["scene_matches"] = self._scene_matches(status.get("obs_scene"))
        if extra:
            status.update(extra)
        with self._lock:
            self._last_status = status
        log.info("Command result: ok=%s command=%s message=%s", ok, command, message)
        self.publish_status()

    def _publish_discovery(self) -> None:
        client = self._client
        if client is None:
            return
        disc = self.mqtt_cfg.get("discovery_prefix", "homeassistant").rstrip("/")
        device_id = self.mqtt_cfg.get("device_id", "golf_sim_control")
        device_name = self.mqtt_cfg.get("device_name", "Golf SIM Control")
        command_topic = self.mqtt_cfg["command_topic"]
        status_topic = self.mqtt_cfg["status_topic"]
        availability = self._availability_topic()
        device = {
            "identifiers": [device_id],
            "name": device_name,
            "manufacturer": "Local",
            "model": "MQTT SIM Control Agent",
        }

        buttons = [
            ("restart_obs_bridge", "Restart OBS Bridge", "restart_obs", "mdi:restart"),
            ("start_obs", "Start OBS", "start_obs", "mdi:video"),
            ("select_swing_analyzer_scene", "Select Swing Analyzer Scene", "select_swing_analyzer_scene", "mdi:view-dashboard"),
            ("start_replay_buffer", "Start Replay Buffer", "start_replay_buffer", "mdi:record-rec"),
            ("save_replay_buffer", "Save Replay Buffer", "save_replay_buffer", "mdi:content-save"),
            ("restart_swing_analyzer", "Restart Swing Analyzer", "restart_analyzer", "mdi:motion-play"),
        ]
        for object_id, name, payload, icon in buttons:
            config = {
                "name": name,
                "unique_id": f"{device_id}_{object_id}",
                "command_topic": command_topic,
                "payload_press": payload,
                "availability_topic": availability,
                "icon": icon,
                "device": device,
            }
            client.publish(
                f"{disc}/button/{device_id}/{object_id}/config",
                json.dumps(config),
                retain=True,
            )

        sensors = [
            ("status", "SIM Control Status", "{{ 'OK' if value_json.ok else 'ERROR' }}"),
            ("last_command", "SIM Control Last Command", "{{ value_json.last_command }}"),
            ("last_result", "SIM Control Last Result", "{{ value_json.last_result }}"),
            ("obs_running", "SIM Control OBS Running", "{{ value_json.obs_running }}"),
            ("obs_scene", "SIM Control OBS Scene", "{{ value_json.obs_scene }}"),
            ("scene_matches", "SIM Control Scene Matches", "{{ value_json.scene_matches }}"),
        ]
        for object_id, name, tpl in sensors:
            config = {
                "name": name,
                "unique_id": f"{device_id}_{object_id}",
                "state_topic": status_topic,
                "value_template": tpl,
                "availability_topic": availability,
                "device": device,
            }
            client.publish(
                f"{disc}/sensor/{device_id}/{object_id}/config",
                json.dumps(config),
                retain=True,
            )

    def restart_obs(self) -> Dict[str, Any]:
        self._stop_obs()
        time.sleep(float(self.obs_cfg.get("restart_wait_seconds", 4)))
        self._start_obs()
        return {"ok": True, "message": "OBS restart requested"}

    def start_obs(self) -> Dict[str, Any]:
        if self._is_process_running():
            return {"ok": True, "message": "OBS already running"}
        self._start_obs()
        return {"ok": True, "message": "OBS start requested"}

    def select_swing_analyzer_scene(self) -> Dict[str, Any]:
        scene = str(self.obs_cfg.get("swing_analyzer_scene") or "").strip()
        if not scene:
            return {"ok": False, "message": "obs.swing_analyzer_scene is not configured"}
        return self._set_obs_scene(scene)

    def start_replay_buffer(self) -> Dict[str, Any]:
        try:
            client = self._obs_client()
        except Exception as e:
            return {"ok": False, "message": f"OBS connect failed: {e}"}

        if self._is_replay_buffer_active(client) is True:
            return {"ok": True, "message": "Replay buffer already running"}

        try:
            client.start_replay_buffer()
        except Exception as e:
            code = self._extract_obs_code(e)
            if code == 702:
                return {"ok": True, "message": "Replay buffer already running"}
            return {
                "ok": False,
                "message": f"Request StartReplayBuffer returned {code or 'error'}: {e}",
            }
        return {"ok": True, "message": "Replay buffer start requested"}

    def save_replay_buffer(self) -> Dict[str, Any]:
        try:
            client = self._obs_client()
        except Exception as e:
            return {"ok": False, "message": f"OBS connect failed: {e}"}

        if self._is_replay_buffer_active(client) is False:
            return {"ok": False, "message": "Replay buffer is not running"}

        try:
            client.save_replay_buffer()
        except Exception as e:
            code = self._extract_obs_code(e)
            if code == 703:
                return {"ok": False, "message": "Replay buffer is not running"}
            return {
                "ok": False,
                "message": f"Request SaveReplayBuffer returned {code or 'error'}: {e}",
            }
        return {"ok": True, "message": "Replay buffer save requested"}

    def restart_analyzer(self) -> Dict[str, Any]:
        stop_command = str(self.analyzer_cfg.get("stop_command") or "").strip()
        start_command = str(self.analyzer_cfg.get("start_command") or "").strip()
        cwd = str(self.analyzer_cfg.get("working_dir") or "").strip() or None
        task_name = str(self.analyzer_cfg.get("task_name") or "").strip()
        if task_name and not stop_command and not start_command:
            return self._restart_scheduled_task(task_name)
        if not stop_command and not start_command:
            return {
                "ok": False,
                "message": "restart_analyzer is not configured",
            }
        if stop_command:
            self._run_shell(stop_command, cwd=cwd, wait=True)
        if start_command:
            self._run_shell(start_command, cwd=cwd, wait=False)
        return {"ok": True, "message": "Swing Analyzer restart command requested"}

    def _restart_scheduled_task(self, task_name: str) -> Dict[str, Any]:
        command = (
            f"Stop-ScheduledTask -TaskName '{task_name}' -ErrorAction SilentlyContinue; "
            "Start-Sleep -Seconds 1; "
            f"Start-ScheduledTask -TaskName '{task_name}'"
        )
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            check=False,
            capture_output=True,
            text=True,
            creationflags=_no_window_flags(),
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "unknown scheduled task error").strip()
            return {"ok": False, "message": f"Could not restart {task_name}: {detail[:160]}"}
        return {"ok": True, "message": f"Restarted scheduled task: {task_name}"}

    def _is_replay_buffer_active(self, client) -> Optional[bool]:
        try:
            response = client.get_replay_buffer_status()
        except Exception as e:
            log.debug("GetReplayBufferStatus failed: %s", e)
            return None
        value = self._read_attr(response, "output_active", "outputActive")
        if value is None:
            return None
        return bool(value)

    @staticmethod
    def _read_attr(response: Any, *names: str) -> Any:
        for name in names:
            value = getattr(response, name, None)
            if value is not None:
                return value
        if isinstance(response, dict):
            for name in names:
                if response.get(name) is not None:
                    return response.get(name)
        return None

    @staticmethod
    def _extract_obs_code(exc: Exception) -> Optional[int]:
        for attr in ("code", "request_status", "status_code"):
            value = getattr(exc, attr, None)
            if isinstance(value, int):
                return value
            if value is not None and hasattr(value, "code"):
                inner = getattr(value, "code", None)
                if isinstance(inner, int):
                    return inner
        return None

    def _obs_client(self):
        try:
            from obsws_python import ReqClient
        except ImportError as e:
            raise RuntimeError("obsws-python not installed; pip install -r requirements.txt") from e

        ws = self.obs_cfg.get("websocket", {})
        return ReqClient(
            host=ws.get("host", "127.0.0.1"),
            port=int(ws.get("port", 4455)),
            password=ws.get("password") or "",
            timeout=float(ws.get("timeout_seconds", 8)),
        )

    def _get_obs_scene(self, obs_running: Optional[bool] = None) -> Optional[str]:
        if obs_running is None:
            obs_running = self._is_process_running()
        if not obs_running:
            return None
        try:
            response = self._obs_client().get_current_program_scene()
        except Exception as e:
            log.debug("Could not read OBS current scene: %s", e)
            return None
        for attr in ("current_program_scene_name", "currentProgramSceneName", "scene_name", "sceneName"):
            value = getattr(response, attr, None)
            if value:
                return str(value)
        if isinstance(response, dict):
            for key in ("currentProgramSceneName", "current_program_scene_name", "sceneName", "scene_name"):
                value = response.get(key)
                if value:
                    return str(value)
        return None

    def _set_obs_scene(self, scene: str) -> Dict[str, Any]:
        client = self._obs_client()
        setter = getattr(client, "set_current_program_scene", None)
        if setter is None:
            return {"ok": False, "message": "OBS scene switching is not supported"}
        errors = []
        for args, kwargs in (
            ((scene,), {}),
            ((), {"sceneName": scene}),
            ((), {"scene_name": scene}),
        ):
            try:
                setter(*args, **kwargs)
                return {
                    "ok": True,
                    "message": f"OBS scene selected: {scene}",
                    "obs_scene": scene,
                    "scene_matches": True,
                }
            except Exception as e:
                errors.append(str(e))
        return {"ok": False, "message": f"Could not select OBS scene {scene}: {errors[-1]}"}

    def _scene_matches(self, scene: object) -> Optional[bool]:
        required = str(self.obs_cfg.get("swing_analyzer_scene") or "").strip()
        if not required or not scene:
            return None
        return str(scene).strip().casefold() == required.casefold()

    def _is_process_running(self) -> bool:
        process_name = str(self.obs_cfg.get("process_name") or "obs64.exe")
        if os.name == "nt":
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {process_name}"],
                check=False,
                capture_output=True,
                text=True,
                creationflags=_no_window_flags(),
            )
            return process_name.lower() in result.stdout.lower()
        result = subprocess.run(
            ["pgrep", "-f", process_name],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def _stop_obs(self) -> None:
        process_name = str(self.obs_cfg.get("process_name") or "obs64.exe")
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/IM", process_name, "/F"],
                check=False,
                capture_output=True,
                text=True,
                creationflags=_no_window_flags(),
            )
            return
        subprocess.run(["pkill", "-f", process_name], check=False)

    def _start_obs(self) -> None:
        exe = Path(str(self.obs_cfg.get("exe_path") or ""))
        if not exe.exists():
            raise FileNotFoundError(f"OBS executable not found: {exe}")
        cwd = str(self.obs_cfg.get("working_dir") or exe.parent)
        subprocess.Popen(
            [str(exe)],
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )

    def _run_shell(self, command: str, cwd: Optional[str], wait: bool) -> None:
        proc = subprocess.Popen(
            command,
            cwd=cwd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=_no_window_flags(),
        )
        if wait:
            proc.wait(timeout=30)

    def _now(self) -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")


def main() -> int:
    instance_lock = _acquire_single_instance()
    cfg_path = os.environ.get("SIM_CONTROL_CONFIG", "config.yaml")
    cfg = load_config(cfg_path)
    agent = SimControlAgent(cfg)
    agent.start()

    def _shutdown(*_) -> None:
        log.info("Shutting down")
        agent.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    try:
        agent.loop_forever()
        return 0
    finally:
        instance_lock.close()
