# MQTT Contract

## Context From Home Assistant

Topic: `golf/context/current`

Retained JSON payload:

```json
{
  "recording": true,
  "bag_test_active": false,
  "player": "Tyler",
  "club": "Driver",
  "session_mode": "Record",
  "session_id": "2026-05-06T01:05:00Z",
  "bag_test_index": 0,
  "bag_test_shot_count": 0,
  "shots_per_club": 5
}
```

## Raw Shot From Lab PC / OBS Bridge

Topic: `golf/shot/raw`

Publish one JSON message per shot:

```json
{
  "id": "optional-shot-id",
  "timestamp": "2026-05-06T01:05:12Z",
  "carry": 176.4,
  "total": 184.2,
  "offline": -8.1,
  "ball_speed": 119.8,
  "club_speed": 84.2,
  "smash_factor": 1.42,
  "launch_angle": 16.3,
  "launch_direction": -1.8,
  "total_spin": 6210,
  "spin_axis": -4.5,
  "backspin": 6100,
  "sidespin": -310,
  "shot_name": "Draw",
  "shot_rank": "A"
}
```

The logger also accepts common aliases like `ballSpeed`, `launchAngle`, and `golf_ball_speed`.

## Discard Last Shot

Topic: `golf/context/discard_last_shot`

Payload can be `{}`. The logger uses the retained context to discard the last matching shot for the current player/session.

## Summaries From Logger

Per club:

`golf/summary/<player>/<club>`

Bag summary:

`golf/summary/<player>/bag`

Session progress:

`golf/summary/session/<session_id>`

AI-ready export:

`golf/export/<player>/ai`

All summary/export topics are retained so Home Assistant can show the latest analytics without querying SQLite.

Per-club summaries include:

- shot count
- averages for carry, total, offline, ball speed, club speed, smash factor, launch angle, launch direction, spin, and spin axis
- carry, total, and offline confidence ranges (`p10_p90`, `p25_p75`, `min_max`, standard deviation)
- playable carry/total yardage windows
- left/right/center rates
- tendency labels such as `slight left tendency`, `right miss pattern`, or `tight dispersion`
- short `ai_notes`

The AI export wraps the whole player bag in a stable JSON object with schema `nova-golf-ai-export/v1`.
