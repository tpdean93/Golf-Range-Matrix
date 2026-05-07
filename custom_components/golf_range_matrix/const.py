"""Constants for the Golf Range Matrix integration."""

from __future__ import annotations

DOMAIN = "golf_range_matrix"

DEFAULT_NAME = "Golf Range Matrix"
DEFAULT_SHOT_TOPIC = "golf/shot/raw"
DEFAULT_CONTEXT_TOPIC = "golf/context/current"
DEFAULT_STORE_UNRECORDED = False
DEFAULT_SHOTS_PER_CLUB = 5

DEFAULT_SOURCE_ENTITIES = {
    "carry": "sensor.golf_carry",
    "total": "sensor.golf_total",
    "offline": "sensor.golf_offline",
    "ball_speed": "sensor.golf_ball_speed",
    "club_speed": "sensor.golf_clubhead_speed",
    "smash_factor": "sensor.golf_smash_factor",
    "launch_angle": "sensor.golf_launch_angle",
    "launch_direction": "sensor.golf_launch_direction",
    "total_spin": "sensor.golf_total_spin",
    "spin_axis": "sensor.golf_spin_axis",
    "backspin": "sensor.golf_backspin",
    "sidespin": "sensor.golf_sidespin",
    "peak_height": "sensor.golf_peak_height",
    "hang_time": "sensor.golf_hang_time",
    "descent_angle": "sensor.golf_descent_angle",
    "shot_name": "sensor.golf_shot_name",
    "shot_rank": "sensor.golf_shot_rank",
}

CONF_SHOT_TOPIC = "shot_topic"
CONF_CONTEXT_TOPIC = "context_topic"
CONF_STORE_UNRECORDED = "store_unrecorded"
CONF_ENABLE_INFLUX = "enable_influx"
CONF_INFLUX_URL = "influx_url"
CONF_INFLUX_TOKEN = "influx_token"
CONF_INFLUX_ORG = "influx_org"
CONF_INFLUX_BUCKET = "influx_bucket"

PLATFORMS = ["sensor", "select", "switch", "button", "number"]

STORE_FILENAME = "golf_range_matrix.sqlite3"

METRIC_FIELDS: dict[str, dict[str, str | tuple[str, ...] | int]] = {
    "carry": {"name": "Carry", "unit": "yd", "icon": "mdi:golf", "decimals": 1, "aliases": ("carry", "golf_carry", "carry_yards", "estimated_carry")},
    "total": {"name": "Total", "unit": "yd", "icon": "mdi:map-marker-distance", "decimals": 1, "aliases": ("total", "golf_total", "total_yards", "distance")},
    "offline": {"name": "Offline", "unit": "yd", "icon": "mdi:axis-arrow", "decimals": 1, "aliases": ("offline", "golf_offline", "offline_yards")},
    "ball_speed": {"name": "Ball Speed", "unit": "mph", "icon": "mdi:speedometer", "decimals": 1, "aliases": ("ball_speed", "golf_ball_speed", "ballSpeed")},
    "club_speed": {"name": "Club Speed", "unit": "mph", "icon": "mdi:golf-tee", "decimals": 1, "aliases": ("club_speed", "clubhead_speed", "golf_clubhead_speed", "clubSpeed")},
    "smash_factor": {"name": "Smash Factor", "unit": "", "icon": "mdi:flash", "decimals": 2, "aliases": ("smash_factor", "golf_smash_factor", "smashFactor")},
    "launch_angle": {"name": "Launch Angle", "unit": "deg", "icon": "mdi:angle-acute", "decimals": 1, "aliases": ("launch_angle", "golf_launch_angle", "launchAngle")},
    "launch_direction": {"name": "Launch Direction", "unit": "deg", "icon": "mdi:arrow-left-right-bold", "decimals": 1, "aliases": ("launch_direction", "golf_launch_direction", "launchDirection")},
    "total_spin": {"name": "Total Spin", "unit": "rpm", "icon": "mdi:rotate-right", "decimals": 0, "aliases": ("total_spin", "golf_total_spin", "totalSpin")},
    "spin_axis": {"name": "Spin Axis", "unit": "deg", "icon": "mdi:axis-arrow", "decimals": 1, "aliases": ("spin_axis", "golf_spin_axis", "spinAxis")},
    "backspin": {"name": "Backspin", "unit": "rpm", "icon": "mdi:rotate-right", "decimals": 0, "aliases": ("backspin", "golf_backspin", "backSpin")},
    "sidespin": {"name": "Sidespin", "unit": "rpm", "icon": "mdi:rotate-3d-variant", "decimals": 0, "aliases": ("sidespin", "golf_sidespin", "sideSpin")},
    "peak_height": {"name": "Peak Height", "unit": "yd", "icon": "mdi:arrow-up-bold", "decimals": 1, "aliases": ("peak_height", "golf_peak_height", "peakHeight")},
    "hang_time": {"name": "Hang Time", "unit": "s", "icon": "mdi:timer-outline", "decimals": 1, "aliases": ("hang_time", "golf_hang_time", "hangTime")},
    "descent_angle": {"name": "Descent Angle", "unit": "deg", "icon": "mdi:angle-acute", "decimals": 1, "aliases": ("descent_angle", "golf_descent_angle", "descentAngle")},
}

TEXT_FIELDS: dict[str, dict[str, str | tuple[str, ...]]] = {
    "shot_name": {"name": "Shot Shape", "icon": "mdi:chart-bell-curve", "aliases": ("shot_name", "golf_shot_name", "shape", "shotShape")},
    "shot_rank": {"name": "Shot Grade", "icon": "mdi:trophy", "aliases": ("shot_rank", "golf_shot_rank", "grade", "rank")},
}

DEFAULT_CATALOG = [
    "Driver",
    "3 Wood",
    "5 Wood",
    "7 Wood",
    "3 Hybrid",
    "4 Hybrid",
    "5 Hybrid",
    "4 Iron",
    "5 Iron",
    "6 Iron",
    "7 Iron",
    "8 Iron",
    "9 Iron",
    "PW",
    "GW",
    "52 Wedge",
    "56 Wedge",
    "60 Wedge",
    "Putter",
]
