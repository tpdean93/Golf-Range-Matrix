# Golf Range Matrix

HACS-installable Home Assistant integration and companion tools for bag mapping, wedge matrix, and virtual driving-range workflows.

This repo contains:

- `custom_components/golf_range_matrix/`: the HACS custom integration with SQLite storage, native entities, services, bundled cards, dashboard templates, and optional InfluxDB export.
- `custom-cards/`: Lovelace cards for shot tracing, metric panels, history, session controls, bag building, and wedge matrix.
- `scripts/nova_shot_logger.py`: local MQTT-to-SQLite shot logger for per-player/per-club shot history.
- `docs/hacs-integration.md`: install, migration, backup, and release notes for the integration.
- `docs/mqtt-contract.md`: MQTT topics and payloads for the HA dashboard and lab PC bridge.
- `docs/home-assistant.md`: helper/card setup notes.
- `docs/dashboard-package.md`: dashboard layout and entity assumptions.

## HACS Integration

The recommended product path is now `Golf Range Matrix` as a Home Assistant custom integration:

1. Add this repo to HACS as a custom integration repository.
2. Install `Golf Range Matrix`.
3. Restart Home Assistant.
4. Add `Golf Range Matrix` from Settings > Devices & services.
5. Add `/golf_range_matrix/golf-range-matrix-cards.js` as a Lovelace module resource or use the bundled dashboard template at `/golf_range_matrix/dashboards/golf-range-matrix-dashboard.json`.

The integration stores app data in `golf_range_matrix.sqlite3` under the Home Assistant config directory. Profiles, bags, club metadata, wedge matrices, shots, and summaries are no longer stored in mutable chunked `input_text` helpers.

## Run The Logger

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python scripts\nova_shot_logger.py --host homeassistant.local
```

Set `MQTT_USERNAME` and `MQTT_PASSWORD` in `.env` if your broker requires authentication.

## Data Flow

1. Home Assistant publishes retained context to `golf/context/current`.
2. The lab PC / OBS bridge publishes each shot to `golf/shot/raw`.
3. The logger combines both payloads and writes SQLite records.
4. The logger publishes retained summaries to `golf/summary/...` and AI-ready exports to `golf/export/...`.
5. Home Assistant can display those summaries on the Golf Range Matrix dashboard.

By default, only shots with `recording: true` in the HA context are stored. Set `NOVA_STORE_UNRECORDED=true` to keep every shot.

## Analytics / AI Export

The logger publishes richer per-club analytics after every recorded or discarded shot:

- `golf/summary/<player>/<club>`: club averages, confidence windows, tendencies, and playable yardage.
- `golf/summary/<player>/bag`: all club summaries for the player.
- `golf/export/<player>/ai`: AI-ready bag profile using schema `nova-golf-ai-export/v1`.

The logger also publishes Home Assistant MQTT discovery for bag summaries, allowing the dashboard Results tab to read entities such as `sensor.golf_summary_tyler_bag`.

Discarded shots are excluded from all analytics.

## Short Game / Wedge Matrix

The wedge matrix card lets each player keep a short-game carry chart by wedge and swing type. It only shows wedges that are saved in that player's bag, so the short-game chart stays tied to the bag setup.

The default swings are:

- `Half`
- `Waist`
- `Shoulder`
- `Full`

Each cell can store a number or a range, such as `74/80`, matching the kind of wedge card you showed.

The card can also capture 5 live carry readings for a selected wedge/swing cell and fill the cell with the average. This is driven from the HA dashboard and uses `sensor.golf_carry`.
