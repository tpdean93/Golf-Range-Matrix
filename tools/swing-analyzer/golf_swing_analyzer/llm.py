"""Local LLM coaching summary (Ollama-style /api/generate)."""
from __future__ import annotations

import json
import logging
import base64
from pathlib import Path
from typing import Any, Dict, Optional

import requests

log = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are a golf swing analysis assistant. "
    "Do not claim certainty from limited camera data. "
    "Use NOVA for club/ball metrics and deterministic pose scores for body mechanics. "
    "Do not invent measurements that are not present in the analysis JSON. "
    "Explain cause and effect briefly and give one practical drill. "
    "Reply with strict JSON only, matching the requested schema."
)


def _short_error(text: str, limit: int = 240) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3] + "..."


def _sample_positions(frame_count: int, count: int) -> list[int]:
    if frame_count <= 0 or count <= 0:
        return []
    if count == 1:
        return [frame_count // 2]
    return sorted({round(i * (frame_count - 1) / (count - 1)) for i in range(count)})


def _video_frames(path: str, count: int, max_width: int, quality: int) -> list[str]:
    """Return base64 JPEG frames for Ollama vision models."""
    video = Path(path)
    if not video.exists() or count <= 0:
        return []
    try:
        import cv2
    except ImportError:
        log.warning("OpenCV is not available; LLM visual frames skipped")
        return []

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        return []
    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        images: list[str] = []
        for idx in _sample_positions(total, count):
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            height, width = frame.shape[:2]
            if width > max_width:
                scale = max_width / float(width)
                frame = cv2.resize(
                    frame,
                    (max_width, max(1, int(height * scale))),
                    interpolation=cv2.INTER_AREA,
                )
            ok, buf = cv2.imencode(
                ".jpg",
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), max(35, min(95, quality))],
            )
            if ok:
                images.append(base64.b64encode(buf).decode("ascii"))
        return images
    finally:
        cap.release()


def _collect_visual_frames(cfg: Dict[str, Any], analysis: Dict[str, Any]) -> list[str]:
    if not cfg.get("send_video_frames", True):
        return []
    max_images = int(cfg.get("max_visual_frames", 8) or 0)
    if max_images <= 0:
        return []
    max_width = int(cfg.get("visual_frame_max_width", 960) or 960)
    quality = int(cfg.get("visual_frame_jpeg_quality", 72) or 72)

    raw_video = analysis.get("raw_video")
    annotated_video = analysis.get("annotated_video")
    paths = [p for p in (raw_video, annotated_video) if p and Path(str(p)).exists()]
    if not paths:
        return []
    if len(paths) == 1:
        return _video_frames(str(paths[0]), max_images, max_width, quality)

    first_count = max(1, max_images // 2)
    images = _video_frames(str(paths[0]), first_count, max_width, quality)
    images.extend(_video_frames(str(paths[1]), max_images - len(images), max_width, quality))
    return images[:max_images]


def generate_summary(cfg: Dict[str, Any], analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not cfg.get("enabled"):
        return None

    endpoint = cfg.get("endpoint")
    model = cfg.get("model", "trinity")
    timeout = int(cfg.get("timeout_seconds", 60))
    if not endpoint:
        return {"llm_status": "not_configured", "llm_error": "LLM endpoint is empty"}

    images = _collect_visual_frames(cfg, analysis)

    user_prompt = (
        "Analyze this golf swing.\n\n"
        f"Club: {analysis.get('club')}\n"
        f"Camera angle: {analysis.get('camera_angle')}\n"
        f"NOVA metrics: {json.dumps(analysis.get('nova', {}))}\n"
        f"Body metrics: {json.dumps(analysis.get('body', {}))}\n"
        f"Advanced traces: {json.dumps(analysis.get('advanced', {}))}\n"
        f"Swing scores: {json.dumps(analysis.get('scores', {}))}\n"
        f"Score summary: {analysis.get('score_summary')}\n"
        f"Detected faults: {json.dumps(analysis.get('faults', []))}\n\n"
        f"Visual frames attached: {len(images)}. When images are attached, they are sampled "
        "from the raw swing video and the annotated/marker video. Use the raw golfer motion "
        "as primary evidence; marker overlays may be approximate or temporarily inaccurate. "
        "Review the sequence across as many attached frames as needed before deciding the priority issue.\n"
        "Treat hip depth and balance as camera-specific trend metrics, not true 3D measurements.\n"
        "Reply with JSON only:\n"
        "{\n"
        '  "priority_fault": "...",\n'
        '  "why_it_matters": "...",\n'
        '  "evidence": ["...", "..."],\n'
        '  "drill": "...",\n'
        '  "confidence": "low|medium|high"\n'
        "}"
    )

    body = {
        "model": model,
        "system": SYSTEM_PROMPT,
        "prompt": user_prompt,
        "stream": False,
        "format": "json",
    }
    if images:
        body["images"] = images
    try:
        r = requests.post(endpoint, json=body, timeout=timeout)
        if r.status_code >= 400:
            error = _short_error(f"LLM {endpoint} returned HTTP {r.status_code}")
            log.warning(error)
            if images:
                log.warning("Retrying LLM without visual frames; model may not support vision")
                body.pop("images", None)
                r = requests.post(endpoint, json=body, timeout=timeout)
                if r.status_code >= 400:
                    error = _short_error(
                        f"LLM {endpoint} returned HTTP {r.status_code} without visual frames"
                    )
                    log.warning(error)
                    return {
                        "llm_status": "failed",
                        "llm_error": error,
                        "visual_frames_sent": len(images),
                    }
            else:
                return {
                    "llm_status": "failed",
                    "llm_error": error,
                    "visual_frames_sent": 0,
                }
        data = r.json()
    except Exception as e:
        error = _short_error(f"LLM call failed: {e}")
        log.warning(error)
        return {
            "llm_status": "failed",
            "llm_error": error,
            "visual_frames_sent": len(images),
        }

    response = data.get("response") or data.get("message", {}).get("content")
    if not response:
        return {
            "llm_status": "empty_response",
            "llm_error": "LLM response did not include response/message.content",
            "visual_frames_sent": len(images),
        }

    try:
        parsed = json.loads(response)
        if isinstance(parsed, dict):
            parsed["llm_status"] = "ok"
            parsed["llm_error"] = ""
            parsed["visual_frames_sent"] = len(images)
            return parsed
    except Exception:
        log.info("LLM response was not valid JSON; returning raw text")
        return {
            "summary": response.strip(),
            "confidence": "low",
            "llm_status": "raw_text",
            "llm_error": "",
            "visual_frames_sent": len(images),
        }
    return {
        "llm_status": "invalid_response",
        "llm_error": "LLM response parsed to a non-object JSON value",
        "visual_frames_sent": len(images),
    }
