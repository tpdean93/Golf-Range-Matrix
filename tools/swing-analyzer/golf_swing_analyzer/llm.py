"""Local LLM coaching summary (Ollama-style /api/generate)."""
from __future__ import annotations

import json
import logging
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


def generate_summary(cfg: Dict[str, Any], analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not cfg.get("enabled"):
        return None

    endpoint = cfg.get("endpoint")
    model = cfg.get("model", "trinity")
    timeout = int(cfg.get("timeout_seconds", 60))
    if not endpoint:
        return None

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
    try:
        r = requests.post(endpoint, json=body, timeout=timeout)
        if r.status_code >= 400:
            log.warning("LLM %s returned %s", endpoint, r.status_code)
            return None
        data = r.json()
    except Exception as e:
        log.warning("LLM call failed: %s", e)
        return None

    response = data.get("response") or data.get("message", {}).get("content")
    if not response:
        return None

    try:
        parsed = json.loads(response)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        log.info("LLM response was not valid JSON; returning raw text")
        return {"summary": response.strip(), "confidence": "low"}
    return None
