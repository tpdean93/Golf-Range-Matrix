"""Main golf swing analyzer service.

Driven entirely by MQTT (no HTTP shot trigger).

Flow:
  1. MQTTBridge subscribes to golf/shot/raw, golf/context/current,
     and golf/swing/analyzer/enabled.
  2. When the analyzer is enabled and a raw shot arrives, save shot JSON
     and ask OBS to flush the replay buffer.
  3. Watchdog sees the new MP4, queues it for processing.
  4. Worker matches video to shot JSON, runs MediaPipe pose, computes
     metrics, renders annotated video, optionally calls a local LLM,
     publishes the result over MQTT (with HA discovery).
  5. Old swings beyond keep_recent_swings are deleted.

Flask is still used, but only as a tiny static file server so HA can
fetch the annotated MP4s for playback in the dashboard.
"""
from __future__ import annotations

import json
import logging
import os
import queue
import signal
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flask import Flask, abort, jsonify, send_from_directory
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .annotate import annotate_video
from .config import load_config
from .llm import generate_summary
from .metrics import compute_body_metrics, derive_faults, detect_phases
from .mqtt_bridge import MQTTBridge
from .obs_client import OBSClient
from .pose import detect_video_pose

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("analyzer")

VIDEO_EXTS = (".mp4", ".mkv", ".mov", ".flv")


def _safe_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _timestamp_from_filename(name: str) -> Optional[datetime]:
    base = Path(name).stem
    for token in base.replace("-", "_").split("_"):
        if len(token) == 14 and token.isdigit():
            try:
                return datetime.strptime(token, "%Y%m%d%H%M%S")
            except ValueError:
                pass
    parts = base.replace("-", "_").split("_")
    for i in range(len(parts) - 1):
        date = parts[i]
        clock = parts[i + 1]
        if len(date) == 8 and date.isdigit() and len(clock) == 6 and clock.isdigit():
            try:
                return datetime.strptime(date + clock, "%Y%m%d%H%M%S")
            except ValueError:
                pass
    return None


class Analyzer:
    def __init__(self, cfg: Dict[str, Any]) -> None:
        self.cfg = cfg
        self.raw_dir = Path(cfg["paths"]["raw_video_dir"])
        self.annotated_dir = Path(cfg["paths"]["annotated_video_dir"])
        self.shot_dir = Path(cfg["paths"]["shot_data_dir"])
        self.analysis_dir = Path(cfg["paths"]["analysis_dir"])

        self.queue: "queue.Queue[Path]" = queue.Queue()
        self.processed: set[str] = set()
        self.lock = threading.Lock()

        self.obs: Optional[OBSClient] = None
        if cfg.get("obs", {}).get("enabled"):
            self.obs = OBSClient(
                host=cfg["obs"].get("host", "127.0.0.1"),
                port=int(cfg["obs"].get("port", 4455)),
                password=cfg["obs"].get("password", ""),
            )

        self.mqtt = MQTTBridge(cfg.get("mqtt", {}))
        self.mqtt.set_callbacks(
            on_shot=self._on_mqtt_shot,
            on_context=self._on_mqtt_context,
            on_enable=self._on_mqtt_enable,
        )
        self.context: Dict[str, Any] = {}
        # Default to off so a fresh install does not chew through CPU/disk
        # until the user clicks Swing Analyzer in HA.
        self.enabled: bool = False

    # ---------- MQTT handlers ----------
    def _on_mqtt_enable(self, on: bool) -> None:
        self.enabled = on
        log.info("Swing analyzer %s via MQTT", "ENABLED" if on else "disabled")

    def _on_mqtt_context(self, ctx: Dict[str, Any]) -> None:
        self.context = ctx or {}

    def _on_mqtt_shot(self, shot: Dict[str, Any]) -> None:
        if not self.enabled:
            log.debug("Shot ignored - analyzer disabled")
            return

        if "timestamp" not in shot:
            shot["timestamp"] = datetime.now().isoformat(timespec="seconds")

        # Range Matrix context wins for player/club/session - the user
        # actively picks the club there, while Nova's OpenAPI feed often
        # reports a stale default like "Driver".
        for key in ("player", "club", "session_id"):
            ctx_value = self.context.get(key)
            if ctx_value:
                shot[key] = ctx_value
            elif key not in shot:
                shot[key] = None

        stamp = _safe_stamp()
        shot_path = self.shot_dir / f"shot_{stamp}.json"
        try:
            with shot_path.open("w", encoding="utf-8") as f:
                json.dump(shot, f, indent=2)
            log.info("Stored shot data: %s", shot_path)
        except Exception as e:
            log.warning("Could not save shot json: %s", e)
            return

        if self.obs and self.cfg.get("obs", {}).get("save_replay_on_shot", True):
            ok = self.obs.save_replay()
            log.info("OBS SaveReplayBuffer requested: ok=%s", ok)
        else:
            log.info("OBS replay save skipped (disabled)")

    # ---------- Worker ----------
    def worker_loop(self) -> None:
        while True:
            video_path = self.queue.get()
            if video_path is None:
                break
            try:
                self.process_video(video_path)
            except Exception as e:
                log.exception("Failed to process %s: %s", video_path, e)
            finally:
                self.queue.task_done()

    def enqueue_video(self, path: Path) -> None:
        key = str(path.resolve())
        with self.lock:
            if key in self.processed:
                return
            self.processed.add(key)
        if not self.enabled:
            log.info("Video %s arrived but analyzer disabled; skipping", path.name)
            return
        log.info("Queued for analysis: %s", path)
        self.queue.put(path)

    def _wait_for_stable_file(self, path: Path, timeout: float = 20.0) -> bool:
        deadline = time.time() + timeout
        last_size = -1
        while time.time() < deadline:
            try:
                size = path.stat().st_size
            except FileNotFoundError:
                time.sleep(0.5)
                continue
            if size == last_size and size > 0:
                return True
            last_size = size
            time.sleep(0.5)
        return False

    def _find_matching_shot(self, video_path: Path) -> Optional[Tuple[Path, Dict[str, Any]]]:
        max_diff = float(self.cfg["matching"]["max_time_difference_seconds"])
        try:
            video_mtime = datetime.fromtimestamp(video_path.stat().st_mtime)
        except Exception:
            video_mtime = datetime.now()

        candidates: List[Tuple[float, Path, Dict[str, Any]]] = []
        for shot_file in self.shot_dir.glob("shot_*.json"):
            try:
                with shot_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            ts_raw = data.get("timestamp")
            ts: Optional[datetime] = None
            if ts_raw:
                try:
                    ts = datetime.fromisoformat(str(ts_raw).replace("Z", ""))
                except Exception:
                    ts = None
            if ts is None:
                ts = _timestamp_from_filename(shot_file.name) or datetime.fromtimestamp(
                    shot_file.stat().st_mtime
                )
            diff = abs((ts - video_mtime).total_seconds())
            if diff <= max_diff:
                candidates.append((diff, shot_file, data))

        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0])
        _, path, data = candidates[0]
        return path, data

    def process_video(self, video_path: Path) -> None:
        log.info("Processing %s", video_path)
        if not self._wait_for_stable_file(video_path, timeout=float(
            self.cfg["matching"].get("wait_for_video_seconds", 20)
        )):
            log.warning("File never stabilized: %s", video_path)
            return

        shot_match = self._find_matching_shot(video_path)
        if shot_match is None:
            log.warning("No matching shot JSON for %s", video_path)
            shot: Dict[str, Any] = {}
        else:
            shot_file, shot = shot_match
            log.info("Matched shot file: %s", shot_file.name)

        try:
            frames, width, height, fps, total = detect_video_pose(
                str(video_path),
                sample_rate=int(self.cfg["camera"]["fps_sample_rate"]),
            )
        except Exception as e:
            log.exception("Pose detection failed: %s", e)
            return

        phases = detect_phases(frames)
        body = compute_body_metrics(
            frames=frames,
            phases=phases,
            fps=fps,
            width=width,
            camera_angle=self.cfg["camera"]["angle"],
        )
        faults = derive_faults(body, shot)

        clip_start, clip_end = self._swing_clip_range(frames, phases, fps)

        stamp = video_path.stem
        annotated_path = self.annotated_dir / f"{stamp}_annotated.mp4"
        annotated_ok = False
        try:
            annotate_video(
                video_path=str(video_path),
                out_path=str(annotated_path),
                frames=frames,
                phases=phases,
                body_metrics=body,
                nova=shot,
                faults=faults,
                clip_start_frame=clip_start,
                clip_end_frame=clip_end,
                slow_motion_factor=float(
                    self.cfg.get("annotation", {}).get("slow_motion_factor", 1.0)
                ),
            )
            annotated_ok = True
        except Exception as e:
            log.exception("Annotation failed: %s", e)

        public = (self.cfg.get("server", {}).get("public_base_url") or "").rstrip("/")
        annotated_url = (
            f"{public}/videos/annotated/{annotated_path.name}"
            if annotated_ok and public else None
        )
        raw_url = f"{public}/videos/raw/{video_path.name}" if public else None

        analysis: Dict[str, Any] = {
            "id": stamp,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "player": shot.get("player") or self.context.get("player"),
            "club": shot.get("club"),
            "camera_angle": self.cfg["camera"]["angle"],
            "raw_video": str(video_path),
            "annotated_video": str(annotated_path) if annotated_ok else None,
            "raw_url": raw_url,
            "annotated_url": annotated_url,
            "shot": shot,
            "body": body,
            "faults": faults,
            "phases": {
                "address_idx": phases.address_idx,
                "top_idx": phases.top_idx,
                "impact_idx": phases.impact_idx,
                "finish_idx": phases.finish_idx,
            },
        }
        analysis["body_summary"] = _summarize_body(body)
        analysis["faults_text"] = ", ".join(faults) if faults else "none"

        llm_result = generate_summary(self.cfg.get("llm", {}), analysis)
        if llm_result:
            analysis["summary"] = llm_result.get("summary", "")
            analysis["llm"] = llm_result
        else:
            analysis["summary"] = analysis["body_summary"]

        analysis_path = self.analysis_dir / f"{stamp}_analysis.json"
        try:
            with analysis_path.open("w", encoding="utf-8") as f:
                json.dump(analysis, f, indent=2)
            log.info("Analysis written: %s", analysis_path)
        except Exception as e:
            log.warning("Could not write analysis JSON: %s", e)

        recent = self._enforce_retention()
        analysis["recent"] = recent

        if self.mqtt.publish_result(analysis):
            log.info("Published analysis for %s to MQTT", stamp)

    def _swing_clip_range(
        self,
        frames: List[Any],
        phases: Any,
        fps: float,
    ) -> tuple[Optional[int], Optional[int]]:
        """Translate sampled-frame phase indices into a source-video frame
        window of roughly [address - 0.3s, impact + 1.0s], clamped to the
        actual swing motion. Returns (start, end) in source-frame coords,
        or (None, None) if we can't bound it (annotator will use full clip).
        """
        if not frames:
            return None, None
        try:
            fps_eff = float(fps) if fps > 0 else 30.0
            pre_pad = int(0.5 * fps_eff)
            post_pad = int(1.5 * fps_eff)

            start_idx = phases.address_idx if phases.address_idx is not None else 0
            end_idx = (
                phases.impact_idx
                if phases.impact_idx is not None
                else len(frames) - 1
            )
            if start_idx < 0:
                start_idx = 0
            if end_idx >= len(frames):
                end_idx = len(frames) - 1

            start_src = max(0, frames[start_idx].frame_index - pre_pad)
            end_src = frames[end_idx].frame_index + post_pad
            return start_src, end_src
        except Exception:
            return None, None

    # ---------- Retention ----------
    def _enforce_retention(self) -> List[Dict[str, Any]]:
        keep = int(self.cfg.get("retention", {}).get("keep_recent_swings", 5))
        if keep < 1:
            keep = 1

        analyses: List[Tuple[float, Path, Dict[str, Any]]] = []
        for f in self.analysis_dir.glob("*_analysis.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            analyses.append((f.stat().st_mtime, f, data))
        analyses.sort(key=lambda t: t[0], reverse=True)

        recent_summary: List[Dict[str, Any]] = []
        for _, _, data in analyses[:keep]:
            recent_summary.append({
                "id": data.get("id"),
                "timestamp": data.get("timestamp"),
                "player": data.get("player"),
                "club": data.get("club"),
                "annotated_url": data.get("annotated_url"),
                "summary": data.get("summary"),
                "faults_text": data.get("faults_text"),
            })

        for _, analysis_path, data in analyses[keep:]:
            self._delete_swing_files(analysis_path, data)
        return recent_summary

    def _delete_swing_files(self, analysis_path: Path, data: Dict[str, Any]) -> None:
        targets: List[Path] = [analysis_path]
        for k in ("raw_video", "annotated_video"):
            v = data.get(k)
            if v:
                targets.append(Path(v))
        stem = data.get("id")
        if isinstance(stem, str) and stem:
            targets.append(self.shot_dir / f"shot_{stem}.json")
            for sf in self.shot_dir.glob("shot_*.json"):
                if stem in sf.name:
                    targets.append(sf)
        for t in targets:
            try:
                if t.exists():
                    t.unlink()
                    log.info("Retention: deleted %s", t)
            except Exception as e:
                log.debug("Retention delete skipped for %s: %s", t, e)

    # ---------- HTTP video server ----------
    def build_app(self) -> Flask:
        app = Flask(__name__)

        roots = {
            "annotated": self.annotated_dir,
            "raw": self.raw_dir,
        }

        @app.route("/health", methods=["GET"])
        def health():
            return jsonify({
                "ok": True,
                "queued": self.queue.qsize(),
                "enabled": self.enabled,
                "context": self.context,
            })

        @app.route("/videos/<which>/<path:filename>", methods=["GET"])
        def videos(which: str, filename: str):
            root = roots.get(which)
            if root is None:
                abort(404)
            return send_from_directory(root, filename, as_attachment=False)

        @app.route("/recent", methods=["GET"])
        def recent():
            files = sorted(
                self.analysis_dir.glob("*_analysis.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            out = []
            for f in files[: int(self.cfg.get("retention", {}).get("keep_recent_swings", 5))]:
                try:
                    out.append(json.loads(f.read_text(encoding="utf-8")))
                except Exception:
                    continue
            return jsonify(out)

        return app

    # ---------- Folder watcher ----------
    def start_watcher(self) -> Observer:
        analyzer = self

        class Handler(FileSystemEventHandler):
            def on_created(self, event):
                if event.is_directory:
                    return
                p = Path(event.src_path)
                if p.suffix.lower() in VIDEO_EXTS:
                    analyzer.enqueue_video(p)

            def on_moved(self, event):
                if event.is_directory:
                    return
                p = Path(event.dest_path)
                if p.suffix.lower() in VIDEO_EXTS:
                    analyzer.enqueue_video(p)

        observer = Observer()
        observer.schedule(Handler(), str(self.raw_dir), recursive=False)
        observer.start()
        log.info("Watching: %s", self.raw_dir)
        return observer


def _summarize_body(body: Dict[str, Any]) -> str:
    parts: List[str] = []
    head = body.get("head_movement")
    if isinstance(head, dict):
        parts.append(f"head {head.get('severity')}")
    spine = body.get("spine_angle")
    if isinstance(spine, dict):
        parts.append(f"spine {spine.get('severity')} ({spine.get('loss_deg')}°)")
    if body.get("early_extension"):
        parts.append("early ext")
    tempo = body.get("tempo")
    if isinstance(tempo, dict) and tempo.get("backswing_to_downswing_ratio"):
        parts.append(f"tempo {tempo['backswing_to_downswing_ratio']}:1")
    return ", ".join(parts) if parts else "no body issues detected"


def main() -> int:
    cfg_path = os.environ.get("ANALYZER_CONFIG", "config.yaml")
    cfg = load_config(cfg_path)

    analyzer = Analyzer(cfg)
    analyzer.mqtt.start()

    worker = threading.Thread(target=analyzer.worker_loop, daemon=True, name="worker")
    worker.start()
    observer = analyzer.start_watcher()

    app = analyzer.build_app()

    def _shutdown(*_):
        log.info("Shutting down...")
        try:
            analyzer.mqtt.stop()
        except Exception:
            pass
        observer.stop()
        observer.join(timeout=2)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    host = cfg["server"].get("host", "0.0.0.0")
    port = int(cfg["server"].get("port", 8765))
    log.info(
        "Video file server on http://%s:%d (MQTT=%s, broker=%s:%s, enable_topic=%s)",
        host, port,
        cfg.get("mqtt", {}).get("enabled"),
        cfg.get("mqtt", {}).get("host"),
        cfg.get("mqtt", {}).get("port"),
        cfg.get("mqtt", {}).get("enable_topic"),
    )
    app.run(host=host, port=port, threaded=True, use_reloader=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
