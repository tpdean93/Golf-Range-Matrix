# NOVA Bag Builder / Shot Logger

Standalone Home Assistant companion for a NOVA launch monitor setup.

This repo contains:

- `custom-cards/`: Lovelace cards for shot tracing, metric panels, history, session controls, bag building, and wedge matrix.
- `scripts/nova_shot_logger.py`: local MQTT-to-SQLite shot logger for per-player/per-club shot history.
- `docs/mqtt-contract.md`: MQTT topics and payloads for the HA dashboard and lab PC bridge.
- `docs/home-assistant.md`: helper/card setup notes.
- `docs/dashboard-package.md`: dashboard layout and entity assumptions.

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
4. The logger publishes retained summaries to `golf/summary/...`.
5. Home Assistant can display those summaries on the NOVA dashboard.

By default, only shots with `recording: true` in the HA context are stored. Set `NOVA_STORE_UNRECORDED=true` to keep every shot.

## Short Game / Wedge Matrix

The wedge matrix card lets each player keep a short-game carry chart by wedge and swing type. It only shows wedges that are saved in that player's bag, so the short-game chart stays tied to the bag setup.

The default swings are:

- `Half`
- `Waist`
- `Shoulder`
- `Full`

Each cell can store a number or a range, such as `74/80`, matching the kind of wedge card you showed.
