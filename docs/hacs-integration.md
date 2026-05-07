# Golf Range Matrix HACS Integration

`Golf Range Matrix` is the Home Assistant product boundary for the launch monitor dashboard. It replaces helper-based prototype storage with integration-owned SQLite, native HA entities, native services, bundled frontend cards, and dashboard templates.

## Install Through HACS

1. In HACS, add this repository as a custom repository with category `Integration`.
2. Install `Golf Range Matrix`.
3. Restart Home Assistant.
4. Go to Settings > Devices & services > Add Integration > Golf Range Matrix.
5. Configure the raw shot MQTT topic, usually `golf/shot/raw`.

The integration depends on Home Assistant's MQTT integration. Configure your MQTT broker in Home Assistant before adding Golf Range Matrix.

## Storage

Canonical data is stored in `golf_range_matrix.sqlite3` in the Home Assistant config directory.

SQLite tables include:

- `players`
- `player_bags`
- `club_metadata`
- `wedge_matrices`
- `shots`
- `app_state`

Do not use mutable `input_text` helpers as canonical storage for profiles, bags, metadata, wedge matrix data, or shot history. The helper import service exists only for one-time migration from the prototype.

## Native Entities

The integration exposes:

- `sensor.golf_range_matrix_range_matrix_carry`, `sensor.golf_range_matrix_range_matrix_total`, `sensor.golf_range_matrix_range_matrix_ball_speed`, `sensor.golf_range_matrix_range_matrix_club_speed`, and other live metrics.
- `sensor.golf_range_matrix_range_matrix_latest_shot` with the full latest shot as attributes.
- `sensor.golf_range_matrix_range_matrix_player_bag_summary` with the active player's club summaries as attributes.
- `sensor.golf_range_matrix_range_matrix_workflow` for session mode and progress attributes.
- `select.golf_range_matrix_range_matrix_active_player` and `select.golf_range_matrix_range_matrix_active_club`.
- `switch.golf_range_matrix_range_matrix_recording`.
- `button.golf_range_matrix_range_matrix_map_club`, `button.golf_range_matrix_range_matrix_bag_test`, `button.golf_range_matrix_range_matrix_discard_last_shot`, and `button.golf_range_matrix_range_matrix_stop_session`.
- `number.golf_range_matrix_range_matrix_shots_per_club`.

Entity IDs can still be adjusted by Home Assistant if there are naming conflicts, but these are the intended defaults.

## Services

Native services replace helper scripts and direct helper writes:

- `golf_range_matrix.save_profile`
- `golf_range_matrix.save_bag`
- `golf_range_matrix.save_club_metadata`
- `golf_range_matrix.save_wedge_matrix`
- `golf_range_matrix.start_mapping`
- `golf_range_matrix.start_bag_test`
- `golf_range_matrix.stop_session`
- `golf_range_matrix.discard_last_shot`
- `golf_range_matrix.import_helpers`
- `golf_range_matrix.export_backup`
- `golf_range_matrix.import_backup`
- `golf_range_matrix.create_dashboard`

Use `golf_range_matrix.import_helpers` once after installing if you want to salvage valid data from the old `input_text.golf_*` helper chunks.

## Frontend Cards

The integration serves bundled cards from:

```text
/golf_range_matrix/golf-range-matrix-cards.js
```

Add that as a Lovelace module resource. It registers:

- `custom:range-shot-tracer-card`
- `custom:range-metric-panel-card`
- `custom:range-shot-history-card`
- `custom:range-session-control-card`
- `custom:range-bag-builder-card`
- `custom:range-wedge-matrix-card`
- `custom:range-club-results-card`
- `custom:range-swing-video-card`

The service-backed cards call `golf_range_matrix.*` services and read native Golf Range Matrix entities. They do not write to `input_text`.

## Dashboard Template

The bundled template is served from:

```text
/golf_range_matrix/dashboards/golf-range-matrix-dashboard.json
```

Call `golf_range_matrix.create_dashboard` to create a persistent notification with the template/resource paths. The current service deliberately avoids mutating Lovelace storage directly; it packages the template so setup tooling or a future guided dashboard installer can consume it.

## MQTT Bridge

The launch monitor bridge should publish raw shot JSON to the configured topic, default:

```text
golf/shot/raw
```

Golf Range Matrix stores shots only while `switch.golf_range_matrix_range_matrix_recording` is on unless `Store shots while recording is off` is enabled in options.

## Optional InfluxDB Export

InfluxDB is optional. Enable it in integration options and provide URL, token, organization, and bucket.

SQLite remains canonical storage. InfluxDB receives shot telemetry as an analytics sink for Grafana or long-term time-series dashboards. Disabling InfluxDB does not affect core Golf Range Matrix data.

## Backups

Use `golf_range_matrix.export_backup` to return a JSON backup payload containing app state and shot rows. Restore with `golf_range_matrix.import_backup`.

For full Home Assistant backups, include the `golf_range_matrix.sqlite3` file from the config directory.

## Release Checklist

Before publishing a release:

- Install from HACS on a clean Home Assistant instance.
- Add the integration through the UI config flow.
- Confirm entities appear without manually creating helpers.
- Add `/golf_range_matrix/golf-range-matrix-cards.js` as a Lovelace resource.
- Load the bundled dashboard template.
- Record/map shots, restart Home Assistant, and verify profiles, bags, metadata, wedge matrix data, summaries, and latest shot data persist.
- Confirm optional InfluxDB export can be disabled without losing core functionality.
