"""Render an annotated copy of the swing video with skeleton + metric overlays."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from .metrics import SwingPhases
from .pose import FramePose

log = logging.getLogger(__name__)


def _resolve_ffmpeg() -> Optional[str]:
    """Find a ffmpeg binary - prefer imageio-ffmpeg's bundled one, fall back to PATH."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    found = shutil.which("ffmpeg")
    return found


def _transcode_to_h264(src: str, dst: str, slow_motion_factor: float = 1.0) -> bool:
    """Transcode an OpenCV-written MP4 (mp4v / MPEG-4 Part 2) to H.264 so
    browsers and Home Assistant can actually play it.

    slow_motion_factor < 1.0 stretches the timeline (0.5 = half-speed).
    """
    ffmpeg = _resolve_ffmpeg()
    if not ffmpeg:
        log.warning("ffmpeg not available - leaving annotated video as mp4v "
                    "(may not play in browsers)")
        try:
            os.replace(src, dst)
            return True
        except Exception as e:
            log.warning("Could not move temp annotated video: %s", e)
            return False

    factor = float(slow_motion_factor or 1.0)
    if factor <= 0.0:
        factor = 1.0
    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-i", src,
    ]
    if abs(factor - 1.0) > 1e-3:
        # setpts > 1 stretches presentation time, e.g. setpts=2*PTS = 0.5x.
        cmd += ["-vf", f"setpts={1.0 / factor}*PTS"]
    cmd += [
        "-an",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-preset", "veryfast",
        "-crf", "23",
        dst,
    ]
    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            log.warning("ffmpeg transcode failed (rc=%s): %s",
                        result.returncode, result.stderr.strip()[:300])
            return False
        try:
            os.remove(src)
        except OSError:
            pass
        return True
    except Exception as e:
        log.warning("ffmpeg transcode exception: %s", e)
        return False


SKELETON_EDGES = [
    ("left_shoulder", "right_shoulder"),
    ("left_hip", "right_hip"),
    ("left_shoulder", "left_elbow"),
    ("left_elbow", "left_wrist"),
    ("right_shoulder", "right_elbow"),
    ("right_elbow", "right_wrist"),
    ("left_shoulder", "left_hip"),
    ("right_shoulder", "right_hip"),
    ("left_hip", "left_knee"),
    ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"),
    ("right_knee", "right_ankle"),
]


def _phase_label(idx: int, phases: SwingPhases, impact_pad_frames: int = 6) -> str:
    if phases.address_idx is not None and idx <= phases.address_idx:
        return "ADDRESS"
    if phases.top_idx is not None and idx <= phases.top_idx:
        return "BACKSWING"
    if phases.impact_idx is not None and idx <= phases.impact_idx:
        return "DOWNSWING"
    if (
        phases.impact_idx is not None
        and idx <= phases.impact_idx + impact_pad_frames
    ):
        return "IMPACT"
    return "FOLLOW THROUGH"


def annotate_video(
    video_path: str,
    out_path: str,
    frames: List[FramePose],
    phases: SwingPhases,
    body_metrics: Dict[str, object],
    advanced_metrics: Optional[Dict[str, object]],
    nova: Dict[str, object],
    faults: List[str],
    clip_start_frame: Optional[int] = None,
    clip_end_frame: Optional[int] = None,
    slow_motion_factor: float = 1.0,
    overlay_options: Optional[Dict[str, object]] = None,
    side_by_side: bool = True,
) -> bool:
    import cv2

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        log.error("Could not open video for annotation: %s", video_path)
        return False

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    if clip_start_frame is None or clip_start_frame < 0:
        clip_start_frame = 0
    if clip_end_frame is None or clip_end_frame <= 0:
        clip_end_frame = total_frames - 1
    if total_frames > 0:
        clip_end_frame = min(clip_end_frame, total_frames - 1)
    if clip_end_frame < clip_start_frame:
        clip_end_frame = clip_start_frame

    out = Path(out_path)
    temp_path = out.with_name(out.stem + "__tmp_mp4v.mp4")

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out_width = width * 2 if side_by_side else width
    writer = cv2.VideoWriter(str(temp_path), fourcc, fps, (out_width, height))

    pose_by_idx: Dict[int, FramePose] = {f.frame_index: f for f in frames}
    last_pose: Optional[FramePose] = None
    overlays = overlay_options or {}

    def _src(sample_idx: Optional[int]) -> Optional[int]:
        if sample_idx is None or sample_idx < 0 or sample_idx >= len(frames):
            return None
        return frames[sample_idx].frame_index

    src_phases = SwingPhases(
        address_idx=_src(phases.address_idx),
        top_idx=_src(phases.top_idx),
        impact_idx=_src(phases.impact_idx),
        finish_idx=_src(phases.finish_idx),
    )

    if clip_start_frame > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, clip_start_frame)

    idx = clip_start_frame - 1
    written = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            idx += 1
            if idx > clip_end_frame:
                break
            if idx < clip_start_frame:
                continue

            raw_panel = frame.copy() if side_by_side else None

            pose = pose_by_idx.get(idx, last_pose)
            if pose is not None:
                last_pose = pose
                _draw_skeleton(frame, pose)
                _draw_lines(frame, pose)
            if overlays.get("advanced", True) and isinstance(advanced_metrics, dict):
                _draw_advanced_overlays(frame, idx, advanced_metrics, overlays)

            _draw_hud(
                frame,
                idx,
                src_phases,
                body_metrics,
                advanced_metrics or {},
                nova,
                faults,
            )

            if side_by_side and raw_panel is not None:
                _draw_panel_label(raw_panel, "RAW", "right")
                _draw_panel_label(frame, "ANALYZED", "right")
                composite = cv2.hconcat([raw_panel, frame])
                writer.write(composite)
            else:
                writer.write(frame)
            written += 1
    finally:
        cap.release()
        writer.release()

    log.info(
        "Annotated clip: %d frames written (source range %d..%d of %d)",
        written, clip_start_frame, clip_end_frame, total_frames,
    )

    transcoded = _transcode_to_h264(
        str(temp_path), str(out), slow_motion_factor=slow_motion_factor
    )
    if transcoded:
        log.info(
            "Annotated video written (h264, %.2fx speed): %s",
            slow_motion_factor, out,
        )
    else:
        log.warning("Annotated video left as mp4v: %s", temp_path)
    return transcoded


def _draw_panel_label(frame, text: str, position: str = "right") -> None:
    """Draw a small labelled banner on a panel (RAW / ANALYZED)."""
    import cv2

    h, w = frame.shape[:2]
    pad_x = 12
    pad_y = 8
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.6
    thickness = 2
    (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
    box_w = tw + pad_x * 2
    box_h = th + pad_y * 2

    if position == "right":
        x1 = w - box_w - 12
    else:
        x1 = 12
    y1 = 12
    x2 = x1 + box_w
    y2 = y1 + box_h

    overlay = frame.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 200), 1)
    cv2.putText(
        frame, text,
        (x1 + pad_x, y1 + pad_y + th),
        font, scale, (0, 255, 200), thickness, cv2.LINE_AA,
    )


def _draw_skeleton(frame, pose: FramePose) -> None:
    import cv2

    color_bone = (0, 255, 200)
    color_joint = (0, 200, 255)

    pts = pose.pixel_landmarks
    for a, b in SKELETON_EDGES:
        if a in pts and b in pts:
            cv2.line(frame, pts[a], pts[b], color_bone, 2)

    for name, (x, y) in pts.items():
        cv2.circle(frame, (x, y), 4, color_joint, -1)


def _draw_lines(frame, pose: FramePose) -> None:
    import cv2

    pts = pose.pixel_landmarks
    if "left_shoulder" in pts and "right_shoulder" in pts:
        cv2.line(frame, pts["left_shoulder"], pts["right_shoulder"], (255, 200, 0), 2)
    if "left_hip" in pts and "right_hip" in pts:
        cv2.line(frame, pts["left_hip"], pts["right_hip"], (255, 100, 100), 2)
    if (
        "left_shoulder" in pts and "right_shoulder" in pts
        and "left_hip" in pts and "right_hip" in pts
    ):
        sh = (
            (pts["left_shoulder"][0] + pts["right_shoulder"][0]) // 2,
            (pts["left_shoulder"][1] + pts["right_shoulder"][1]) // 2,
        )
        hp = (
            (pts["left_hip"][0] + pts["right_hip"][0]) // 2,
            (pts["left_hip"][1] + pts["right_hip"][1]) // 2,
        )
        cv2.line(frame, sh, hp, (200, 200, 255), 2)


def _point(value) -> Optional[tuple[int, int]]:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return (int(value[0]), int(value[1]))
        except (TypeError, ValueError):
            return None
    return None


def _draw_line_dict(frame, line: object, color: tuple[int, int, int], thickness: int = 2) -> None:
    import cv2

    if not isinstance(line, dict):
        return
    start = _point(line.get("start"))
    end = _point(line.get("end"))
    if start and end:
        cv2.line(frame, start, end, color, thickness)


def _draw_polyline(frame, points: List[tuple[int, int]], color: tuple[int, int, int], thickness: int = 2) -> None:
    import cv2

    if len(points) < 2:
        return
    for a, b in zip(points, points[1:]):
        cv2.line(frame, a, b, color, thickness)


def _draw_advanced_overlays(
    frame,
    idx: int,
    package: Dict[str, object],
    overlays: Dict[str, object],
) -> None:
    import cv2

    advanced = package.get("advanced") if isinstance(package, dict) else None
    if not isinstance(advanced, dict):
        return

    pelvis = advanced.get("pelvis_depth_line")
    if overlays.get("pelvis_depth_line", True) and isinstance(pelvis, dict):
        _draw_line_dict(frame, pelvis.get("reference"), (255, 180, 60), 2)
        address = _point(pelvis.get("address_center"))
        impact = _point(pelvis.get("impact_center"))
        if address and impact:
            cv2.circle(frame, address, 6, (255, 180, 60), 2)
            cv2.circle(frame, impact, 6, (80, 255, 255), 2)
            cv2.line(frame, address, impact, (80, 255, 255), 2)
            cv2.putText(frame, "pelvis depth", (address[0] + 8, max(18, address[1] - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 180, 60), 1)

    spine = advanced.get("spine_inclination_line")
    if overlays.get("spine_inclination_line", True) and isinstance(spine, dict):
        _draw_line_dict(frame, spine.get("address"), (120, 180, 255), 2)
        _draw_line_dict(frame, spine.get("impact"), (80, 255, 255), 2)

    head = advanced.get("head_box")
    if overlays.get("head_box", True) and isinstance(head, dict):
        rect = head.get("rect")
        center = _point(head.get("address_center"))
        if isinstance(rect, list) and len(rect) == 4:
            try:
                x1, y1, x2, y2 = [int(v) for v in rect]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (120, 255, 120), 2)
                cv2.putText(frame, "head box", (x1, max(18, y1 - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 255, 120), 1)
            except (TypeError, ValueError):
                pass
        if center:
            cv2.circle(frame, center, 5, (120, 255, 120), 2)

    shoulder_trace = advanced.get("shoulder_plane_trace")
    if overlays.get("shoulder_plane_trace", True) and isinstance(shoulder_trace, list):
        for item in shoulder_trace:
            if not isinstance(item, dict) or item.get("phase") not in {"address", "top", "impact"}:
                continue
            color = (255, 200, 0) if item.get("phase") == "address" else (80, 255, 255)
            _draw_line_dict(frame, item, color, 2)

    hand_trace = advanced.get("hand_path_trace")
    if overlays.get("hand_path_trace", True) and isinstance(hand_trace, list):
        past_points: List[tuple[int, int]] = []
        all_points: List[tuple[int, int]] = []
        for item in hand_trace:
            if not isinstance(item, dict):
                continue
            point = _point([item.get("x"), item.get("y")])
            if not point:
                continue
            all_points.append(point)
            frame_index = item.get("frame_index")
            if isinstance(frame_index, int) and frame_index <= idx:
                past_points.append(point)
        _draw_polyline(frame, all_points, (100, 100, 100), 1)
        _draw_polyline(frame, past_points, (255, 80, 255), 3)
        if past_points:
            cv2.circle(frame, past_points[-1], 5, (255, 80, 255), -1)


def _draw_hud(
    frame,
    idx: int,
    phases: SwingPhases,
    body_metrics: Dict[str, object],
    advanced_metrics: Dict[str, object],
    nova: Dict[str, object],
    faults: List[str],
) -> None:
    import cv2

    h, w = frame.shape[:2]
    overlay = frame.copy()
    panel_w = 300
    cv2.rectangle(overlay, (0, 0), (panel_w, h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)

    y = 25
    line_h = 22

    cv2.putText(frame, _phase_label(idx, phases), (10, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    y += line_h + 5

    nova_lines = [
        ("Club", nova.get("club"), "{}", ""),
        ("Carry", nova.get("carry"), "{:.1f}", " yd"),
        ("Path", nova.get("club_path"), "{:+.1f}", " deg"),
        ("Face", nova.get("face_angle") or nova.get("face_to_target"),
         "{:+.1f}", " deg"),
        ("F2P", nova.get("face_to_path"), "{:+.1f}", " deg"),
        ("AoA", nova.get("attack_angle"), "{:+.1f}", " deg"),
    ]
    for label, val, fmt, unit in nova_lines:
        if val is None or val == "":
            continue
        try:
            text = f"{label}: {fmt.format(float(val))}{unit}" \
                if fmt != "{}" else f"{label}: {val}"
        except (TypeError, ValueError):
            text = f"{label}: {val}"
        cv2.putText(
            frame,
            text,
            (10, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
        )
        y += line_h

    y += 5
    cv2.putText(frame, "BODY", (10, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 255, 180), 1)
    y += line_h

    body_lines: List[str] = []
    head = body_metrics.get("head_movement") if isinstance(body_metrics, dict) else None
    if isinstance(head, dict):
        body_lines.append(f"Head: {head.get('severity')}")
    spine = body_metrics.get("spine_angle") if isinstance(body_metrics, dict) else None
    if isinstance(spine, dict):
        body_lines.append(
            f"Spine loss: {spine.get('loss_deg')} deg ({spine.get('severity')})"
        )
    if body_metrics.get("early_extension"):
        body_lines.append("Early extension: yes")
    tempo = body_metrics.get("tempo") if isinstance(body_metrics, dict) else None
    if isinstance(tempo, dict) and tempo.get("backswing_to_downswing_ratio"):
        body_lines.append(f"Tempo: {tempo['backswing_to_downswing_ratio']}:1")
    score_summary = (
        advanced_metrics.get("score_summary")
        if isinstance(advanced_metrics, dict)
        else None
    )
    if score_summary:
        body_lines.append(str(score_summary))

    for line in body_lines:
        cv2.putText(
            frame,
            line,
            (10, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (220, 255, 220),
            1,
        )
        y += line_h - 2

    if faults:
        y += 5
        cv2.putText(frame, "FAULTS", (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 255), 1)
        y += line_h
        for fault in faults[:5]:
            cv2.putText(
                frame,
                f"- {fault}",
                (10, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (220, 220, 255),
                1,
            )
            y += line_h - 2
