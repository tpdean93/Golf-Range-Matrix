# NOVA Bag Builder / Shot Logger

Standalone Home Assistant companion for a NOVA launch monitor setup.

This repo contains:

- `custom-cards/nova-bag-builder-card.js`: Lovelace custom card for per-player bag building, active club selection, custom clubs, and PGA 14-club limit enforcement.
- `scripts/nova_shot_logger.py`: local MQTT-to-SQLite shot logger for per-player/per-club shot history.
- `docs/mqtt-contract.md`: MQTT topics and payloads for the HA dashboard and lab PC bridge.
- `docs/home-assistant.md`: helper/card setup notes.

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
