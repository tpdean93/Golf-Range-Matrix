"""Body metrics derived from pose frames."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from .pose import FramePose, angle_deg, midpoint

log = logging.getLogger(__name__)


@dataclass
class SwingPhases:
    address_idx: Optional[int]
    top_idx: Optional[int]
    impact_idx: Optional[int]
    finish_idx: Optional[int]


def _have(frame: FramePose, *names: str, min_vis: float = 0.4) -> bool:
    for n in names:
        if n not in frame.pixel_landmarks:
            return False
        if frame.visibility.get(n, 0.0) < min_vis:
            return False
    return True


def _wrist_xy(frame: FramePose) -> Optional[Tuple[float, float]]:
    """Return midpoint of available wrists in pixels."""
    if _have(frame, "left_wrist", "right_wrist"):
        return midpoint(
            frame.pixel_landmarks["left_wrist"],
            frame.pixel_landmarks["right_wrist"],
        )
    if _have(frame, "left_wrist"):
        return tuple(map(float, frame.pixel_landmarks["left_wrist"]))
    if _have(frame, "right_wrist"):
        return tuple(map(float, frame.pixel_landmarks["right_wrist"]))
    return None


def detect_phases(frames: List[FramePose]) -> SwingPhases:
    """Velocity-based phase detection.

    Replay buffer clips usually have many seconds of pre/post motion (walking
    in, addressing, swinging, walking out). A naive "min wrist y" or
    "first stable frame" approach picks up walking poses and gives absurd
    backswing:downswing ratios. Instead we:

      1. Compute smoothed wrist speed per sampled frame.
      2. Pick impact = argmax speed.
      3. Look backward inside a 1.5s pre-impact window for the top
         (smallest wrist Y or speed minimum just before impact).
      4. Walk further backward for the last "calm" segment - that's address.
    """
    if not frames:
        return SwingPhases(None, None, None, None)

    n = len(frames)
    finish_idx = n - 1
    if n < 3:
        return SwingPhases(0, None, None, finish_idx)

    # 1. Per-frame wrist position + speed
    wrists: List[Optional[tuple]] = [_wrist_xy(f) for f in frames]
    speeds: List[float] = [0.0] * n
    for i in range(1, n):
        a = wrists[i - 1]
        b = wrists[i]
        if a is None or b is None:
            speeds[i] = 0.0
        else:
            dx, dy = b[0] - a[0], b[1] - a[1]
            speeds[i] = (dx * dx + dy * dy) ** 0.5

    smoothed: List[float] = speeds[:]
    for i in range(2, n - 2):
        smoothed[i] = (
            speeds[i - 2] + speeds[i - 1] + speeds[i] + speeds[i + 1] + speeds[i + 2]
        ) / 5.0

    # The actual ball strike is much faster than walking, placing the ball,
    # or a practice waggle. Use a "stillness then peak" pattern:
    #   walk in -> setup -> *still at address* -> SWING -> done.
    # Find the LAST stillness run, then the peak speed after it.

    sorted_speeds = sorted(s for s in smoothed if s > 0)
    if not sorted_speeds:
        return SwingPhases(0, None, None, finish_idx)
    # 60th percentile is a reasonable "moving" floor; below 30% of that is
    # treated as "still".
    p60 = sorted_speeds[int(len(sorted_speeds) * 0.60)]
    still_threshold = max(1.5, p60 * 0.30)

    still_run_min = 4   # ~4 sampled frames at 30Hz sample = ~0.13s
    address_anchor: Optional[int] = None
    run_len = 0
    for i in range(n):
        if smoothed[i] <= still_threshold:
            run_len += 1
        else:
            if run_len >= still_run_min:
                address_anchor = i - 1   # last still frame in the run
            run_run_reset_marker = True   # noqa: F841 (clarity only)
            run_len = 0
    if run_len >= still_run_min and address_anchor is None:
        address_anchor = n - 1

    # 2. Impact = peak speed AFTER the last stillness run, with a safety
    #    margin against the very last frames.
    margin_end = max(1, n // 30)
    if address_anchor is not None and address_anchor < n - 2:
        impact_search_start = address_anchor + 1
    else:
        impact_search_start = max(2, n // 5)

    impact_search_end = n - margin_end
    if impact_search_end <= impact_search_start:
        impact_search_end = n - 1

    impact_idx = max(
        range(impact_search_start, impact_search_end),
        key=lambda i: smoothed[i],
        default=None,
    )
    if impact_idx is None or smoothed[impact_idx] <= still_threshold:
        # Fall back to global peak if the post-stillness search found nothing.
        impact_idx = max(range(n), key=lambda i: smoothed[i])

    # 3. Top of swing: highest wrist (smallest y) between address and impact.
    top_search_start = address_anchor if address_anchor is not None else max(
        0, impact_idx - 45
    )
    top_idx: Optional[int] = None
    top_y = float("inf")
    for i in range(top_search_start, impact_idx):
        w = wrists[i]
        if w is None:
            continue
        if w[1] < top_y:
            top_y = w[1]
            top_idx = i
    if top_idx is None:
        top_idx = max(top_search_start, impact_idx - 15)

    address_idx = (
        address_anchor if address_anchor is not None
        else max(0, top_idx - 30)
    )

    log.info(
        "Phases: address=%s top=%s impact=%s finish=%s "
        "(n=%d, still_thr=%.2f, peak=%.2f)",
        address_idx, top_idx, impact_idx, finish_idx,
        n, still_threshold, smoothed[impact_idx],
    )
    return SwingPhases(address_idx, top_idx, impact_idx, finish_idx)


def _severity(value: float, low: float, high: float) -> str:
    v = abs(value)
    if v < low:
        return "low"
    if v < high:
        return "moderate"
    return "high"


def _spine_angle_deg(frame: FramePose) -> Optional[float]:
    if not _have(
        frame,
        "left_shoulder", "right_shoulder",
        "left_hip", "right_hip",
        min_vis=0.3,
    ):
        return None
    sh = midpoint(
        frame.pixel_landmarks["left_shoulder"],
        frame.pixel_landmarks["right_shoulder"],
    )
    hp = midpoint(
        frame.pixel_landmarks["left_hip"],
        frame.pixel_landmarks["right_hip"],
    )
    return angle_deg(sh, hp)


def _shoulder_tilt_deg(frame: FramePose) -> Optional[float]:
    if not _have(frame, "left_shoulder", "right_shoulder", min_vis=0.3):
        return None
    ls = frame.pixel_landmarks["left_shoulder"]
    rs = frame.pixel_landmarks["right_shoulder"]
    return angle_deg(ls, rs)


def _knee_angle_deg(frame: FramePose, side: str) -> Optional[float]:
    hip = f"{side}_hip"
    knee = f"{side}_knee"
    ankle = f"{side}_ankle"
    if not _have(frame, hip, knee, ankle, min_vis=0.3):
        return None
    a = np.array(frame.pixel_landmarks[hip], dtype=float)
    b = np.array(frame.pixel_landmarks[knee], dtype=float)
    c = np.array(frame.pixel_landmarks[ankle], dtype=float)
    ba = a - b
    bc = c - b
    denom = (np.linalg.norm(ba) * np.linalg.norm(bc)) or 1.0
    cos_angle = float(np.dot(ba, bc) / denom)
    cos_angle = max(-1.0, min(1.0, cos_angle))
    return float(np.degrees(np.arccos(cos_angle)))


def compute_body_metrics(
    frames: List[FramePose],
    phases: SwingPhases,
    fps: float,
    width: int,
    camera_angle: str = "down_the_line",
) -> Dict[str, object]:
    out: Dict[str, object] = {}

    if not frames or phases.address_idx is None or phases.impact_idx is None:
        return {
            "head_movement": None,
            "spine_angle": None,
            "hip_sway": None,
            "early_extension": None,
            "shoulder_tilt": None,
            "knee_flex": None,
            "tempo": None,
        }

    address = frames[phases.address_idx]
    impact = frames[phases.impact_idx]
    top = frames[phases.top_idx] if phases.top_idx is not None else None

    px_per_unit = max(1.0, width / 100.0)  # ~1% of frame width

    # Head movement
    if _have(address, "nose") and _have(impact, "nose"):
        ax, ay = address.pixel_landmarks["nose"]
        ix, iy = impact.pixel_landmarks["nose"]
        dx = ix - ax
        dy = iy - ay
        out["head_movement"] = {
            "horizontal_px": int(dx),
            "vertical_px": int(dy),
            "horizontal_pct": round(dx / max(width, 1) * 100, 2),
            "severity": _severity(abs(dx) / px_per_unit, 2.0, 5.0),
        }
    else:
        out["head_movement"] = None

    # Spine angle
    spine_address = _spine_angle_deg(address)
    spine_impact = _spine_angle_deg(impact)
    if spine_address is not None and spine_impact is not None:
        loss = spine_address - spine_impact
        out["spine_angle"] = {
            "address_deg": round(spine_address, 1),
            "impact_deg": round(spine_impact, 1),
            "loss_deg": round(loss, 1),
            "severity": _severity(loss, 5.0, 12.0),
        }
    else:
        out["spine_angle"] = None

    # Hip sway / early extension
    if _have(address, "left_hip", "right_hip") and _have(
        impact, "left_hip", "right_hip"
    ):
        a_hip = midpoint(
            address.pixel_landmarks["left_hip"],
            address.pixel_landmarks["right_hip"],
        )
        i_hip = midpoint(
            impact.pixel_landmarks["left_hip"],
            impact.pixel_landmarks["right_hip"],
        )
        sway_x = i_hip[0] - a_hip[0]
        sway_y = i_hip[1] - a_hip[1]
        out["hip_sway"] = {
            "horizontal_px": int(sway_x),
            "vertical_px": int(sway_y),
            "severity": _severity(abs(sway_x) / px_per_unit, 2.0, 5.0),
        }
        if camera_angle == "down_the_line":
            # In DTL, hips moving toward the ball = toward bottom of frame ~ y increases.
            out["early_extension"] = bool(sway_y < -px_per_unit * 1.5)
        else:
            out["early_extension"] = None
    else:
        out["hip_sway"] = None
        out["early_extension"] = None

    # Shoulder tilt
    tilt_address = _shoulder_tilt_deg(address)
    tilt_top = _shoulder_tilt_deg(top) if top is not None else None
    tilt_impact = _shoulder_tilt_deg(impact)
    if tilt_address is not None and tilt_impact is not None:
        out["shoulder_tilt"] = {
            "address_deg": round(tilt_address, 1),
            "top_deg": None if tilt_top is None else round(tilt_top, 1),
            "impact_deg": round(tilt_impact, 1),
        }
    else:
        out["shoulder_tilt"] = None

    # Knee flex change
    knee_data: Dict[str, object] = {}
    for side in ("left", "right"):
        a = _knee_angle_deg(address, side)
        i = _knee_angle_deg(impact, side)
        if a is not None and i is not None:
            knee_data[side] = {
                "address_deg": round(a, 1),
                "impact_deg": round(i, 1),
                "change_deg": round(i - a, 1),
            }
    out["knee_flex"] = knee_data or None

    # Tempo
    if (
        phases.address_idx is not None
        and phases.top_idx is not None
        and phases.impact_idx is not None
    ):
        bs = max(0, phases.top_idx - phases.address_idx)
        ds = max(0, phases.impact_idx - phases.top_idx)
        ratio = (bs / ds) if ds > 0 else None
        out["tempo"] = {
            "frames_address_to_top": int(bs),
            "frames_top_to_impact": int(ds),
            "backswing_to_downswing_ratio": None if ratio is None else round(ratio, 2),
        }
    else:
        out["tempo"] = None

    return out


def derive_faults(body: Dict[str, object], nova: Dict[str, object]) -> List[str]:
    faults: List[str] = []

    head = body.get("head_movement") if isinstance(body, dict) else None
    if isinstance(head, dict) and head.get("severity") in ("moderate", "high"):
        faults.append(f"{head['severity']} head movement")

    spine = body.get("spine_angle") if isinstance(body, dict) else None
    if isinstance(spine, dict) and spine.get("severity") in ("moderate", "high"):
        faults.append(f"{spine['severity']} spine angle loss")

    hip = body.get("hip_sway") if isinstance(body, dict) else None
    if isinstance(hip, dict) and hip.get("severity") == "high":
        faults.append("hip sway through impact")

    if body.get("early_extension"):
        faults.append("possible early extension")

    if isinstance(nova, dict):
        path = nova.get("club_path")
        face_to_path = nova.get("face_to_path")
        if isinstance(path, (int, float)) and path < -2:
            faults.append("out-to-in club path")
        elif isinstance(path, (int, float)) and path > 2:
            faults.append("in-to-out club path")
        if isinstance(face_to_path, (int, float)) and abs(face_to_path) > 4:
            direction = "open" if face_to_path > 0 else "closed"
            faults.append(f"face {direction} to path")

    return faults
