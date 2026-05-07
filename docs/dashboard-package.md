# Dashboard Package

The repo includes the custom dashboard pieces built for the Golf Range Matrix launch monitor dashboard.

## Cards

- `range-shot-tracer-card`: animated 300-yard driving-range shot tracer with carry, total, offline, grade, shot shape, and ball flight animation.
- `range-metric-panel-card`: reusable glass metric panel for scoring numbers, flight window, club delivery, and spin/result blocks.
- `range-shot-history-card`: last-50-shot charts with immediate live buffering plus recorder history.
- `range-session-control-card`: practice/session controls, dynamic player profiles, single-club mapping, and bag-test flow.
- `range-bag-builder-card`: dynamic per-player bag builder with custom clubs and 14-club max.
- `range-wedge-matrix-card`: short-game wedge matrix for swing type and wedge yardages, including 5-shot carry capture.
- `range-club-results-card`: mapped bag results wall with one card per saved club, manual brand/model/image metadata, and live logger summaries.
- `range-swing-video-card`: compact Swing Analyzer toggle and looping annotated swing playback.

## Suggested Views

- `Range Matrix`: main launch monitor view with shot tracer on the left and metric panels/history on the right.
- `Numbers`: raw Open Golf Coach metric tiles for debugging.
- `Practice`: session controls, bag builder, wedge matrix, and MQTT contract.
- `Results`: per-player club cards showing mapped averages, playable yardages, tendencies, confidence, and editable club details.

## Entity Naming Assumptions

The included examples assume Open Golf Coach metrics arrive as:

- `sensor.golf_carry`
- `sensor.golf_total`
- `sensor.golf_offline`
- `sensor.golf_ball_speed`
- `sensor.golf_clubhead_speed`
- `sensor.golf_smash_factor`
- `sensor.golf_launch_angle`
- `sensor.golf_launch_direction`
- `sensor.golf_total_spin`
- `sensor.golf_spin_axis`
- `sensor.golf_peak_height`
- `sensor.golf_hang_time`
- `sensor.golf_descent_angle`
- `sensor.golf_shot_name`
- `sensor.golf_shot_rank`

If another bridge publishes different entity IDs, update the card configs rather than changing the card code.

## Results View Data

The Results view expects the logger to expose retained MQTT summaries through Home Assistant MQTT discovery. For Tyler, the expected entity is:

- `sensor.golf_summary_tyler_bag`

That sensor's attributes contain the retained `golf/summary/tyler/bag` payload, including each mapped club's averages, confidence windows, playable yardage, tendencies, and AI notes. Re-mapping a club updates the retained MQTT topic, which updates the entity and the matching result card.

If Home Assistant generates a device-prefixed MQTT entity such as `sensor.nova_shot_logger_golf_summary_tyler_bag`, the card can read that fallback too.

Manual club details are stored in chunked helpers:

- `input_text.golf_club_metadata_json`
- `input_text.golf_club_metadata_json_2` through `input_text.golf_club_metadata_json_8`

The metadata shape is:

```json
{
  "Tyler": {
    "PW": {
      "brand": "Titleist",
      "model": "Vokey SM10",
      "image_url": "https://example.com/pw.png"
    }
  }
}
```
