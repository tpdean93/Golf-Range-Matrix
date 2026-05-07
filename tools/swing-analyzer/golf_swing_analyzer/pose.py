"""MediaPipe Tasks API pose detection across a video."""
from __future__ import annotations

import logging
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)


# 33 BlazePose landmarks; we only care about the body ones below.
LANDMARK_NAMES = {
    0: "nose",
    11: "left_shoulder", 12: "right_shoulder",
    13: "left_elbow", 14: "right_elbow",
    15: "left_wrist", 16: "right_wrist",
    23: "left_hip", 24: "right_hip",
    25: "left_knee", 26: "right_knee",
    27: "left_ankle", 28: "right_ankle",
}


MODEL_FILENAME = "pose_landmarker_full.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_full/float16/latest/pose_landmarker_full.task"
)


def _models_dir() -> Path:
    here = Path(__file__).resolve().parent.parent
    d = here / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ensure_model() -> Path:
    """Download the Pose Landmarker model file if missing."""
    target = _models_dir() / MODEL_FILENAME
    if target.exists() and target.stat().st_size > 0:
        return target
    log.info("Downloading MediaPipe pose model to %s ...", target)
    tmp = target.with_suffix(".task.part")
    urllib.request.urlretrieve(MODEL_URL, tmp)
    os.replace(tmp, target)
    log.info("Pose model downloaded (%.1f MB)", target.stat().st_size / 1_000_000)
    return target


@dataclass
class FramePose:
    frame_index: int
    timestamp_s: float
    landmarks: Dict[str, Tuple[float, float, float]]
    pixel_landmarks: Dict[str, Tuple[int, int]]
    visibility: Dict[str, float]


def detect_video_pose(
    video_path: str,
    sample_rate: int = 2,
    min_torso_visibility: float = 0.6,
) -> Tuple[List[FramePose], int, int, float, int]:
    """Run MediaPipe Pose Landmarker on every Nth frame.

    Frames where the model latches on to background clutter (a bike, a
    chair, etc.) usually score low on torso visibility. We reject those
    so they don't pollute the velocity / metric calculations.

    Returns (frames, width, height, fps, total_frames).
    """
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python as mp_tasks
    from mediapipe.tasks.python import vision as mp_vision

    model_path = str(ensure_model())

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    sample_rate = max(1, int(sample_rate))
    frames: List[FramePose] = []
    rejected_low_vis = 0

    base_options = mp_tasks.BaseOptions(model_asset_path=model_path)
    options = mp_vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=mp_vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.7,
        min_pose_presence_confidence=0.7,
        min_tracking_confidence=0.6,
    )

    torso_keys = ("left_shoulder", "right_shoulder", "left_hip", "right_hip")

    with mp_vision.PoseLandmarker.create_from_options(options) as landmarker:
        idx = -1
        while True:
            ok, frame_bgr = cap.read()
            if not ok:
                break
            idx += 1
            if idx % sample_rate != 0:
                continue

            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
            timestamp_ms = int((idx / fps) * 1000)
            result = landmarker.detect_for_video(mp_image, timestamp_ms)
            if not result.pose_landmarks:
                continue

            pose_landmarks = result.pose_landmarks[0]

            landmarks: Dict[str, Tuple[float, float, float]] = {}
            pixel_landmarks: Dict[str, Tuple[int, int]] = {}
            visibility: Dict[str, float] = {}

            for i, lm in enumerate(pose_landmarks):
                name = LANDMARK_NAMES.get(i)
                if not name:
                    continue
                landmarks[name] = (float(lm.x), float(lm.y), float(lm.z))
                pixel_landmarks[name] = (
                    int(lm.x * width),
                    int(lm.y * height),
                )
                visibility[name] = float(getattr(lm, "visibility", 1.0) or 1.0)

            torso_scores = [visibility.get(k, 0.0) for k in torso_keys]
            torso_vis = sum(torso_scores) / len(torso_scores) if torso_scores else 0.0
            if torso_vis < min_torso_visibility:
                rejected_low_vis += 1
                continue

            frames.append(
                FramePose(
                    frame_index=idx,
                    timestamp_s=idx / fps,
                    landmarks=landmarks,
                    pixel_landmarks=pixel_landmarks,
                    visibility=visibility,
                )
            )

    cap.release()
    log.info(
        "Pose: %d kept frames, %d rejected (low torso vis), %dx%d @ %.2f fps (total %d)",
        len(frames), rejected_low_vis, width, height, fps, total,
    )
    return frames, width, height, fps, total


def midpoint(a: Tuple[float, float], b: Tuple[float, float]) -> Tuple[float, float]:
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def angle_deg(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Angle of line p1->p2 from horizontal, in degrees, [0, 90]."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    if dx == 0 and dy == 0:
        return 0.0
    angle = np.degrees(np.arctan2(abs(dy), abs(dx)))
    return float(angle)
