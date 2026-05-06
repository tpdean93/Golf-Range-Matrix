# Dashboard Package

The repo includes the custom dashboard pieces built for the NOVA launch monitor dashboard.

## Cards

- `nova-shot-tracer-card`: animated 300-yard driving-range shot tracer with carry, total, offline, grade, shot shape, and ball flight animation.
- `golf-metric-panel-card`: reusable glass metric panel for scoring numbers, flight window, club delivery, and spin/result blocks.
- `golf-shot-history-card`: last-50-shot charts with immediate live buffering plus recorder history.
- `golf-session-control-card`: practice/session controls that follow the selected player's saved bag.
- `nova-bag-builder-card`: per-player bag builder with custom clubs and 14-club max.
- `nova-wedge-matrix-card`: short-game wedge matrix for swing type and wedge yardages.

## Suggested Views

- `NOVA`: main launch monitor view with shot tracer on the left and metric panels/history on the right.
- `Numbers`: raw OpenGolfCoach/NOVA metric tiles for debugging.
- `Practice`: session controls, bag builder, wedge matrix, and MQTT contract.

## Entity Naming Assumptions

The included examples assume OpenGolfCoach/NOVA metrics arrive as:

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
