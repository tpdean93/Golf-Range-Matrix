# Golf Swing Analyzer

Local-only golf swing analysis service for the Range Matrix / NOVA shot logger stack. It subscribes to the same MQTT shot events as Range Matrix, asks OBS to save the replay buffer, runs MediaPipe pose analysis, renders a browser-playable annotated MP4, serves the clip over HTTP, and publishes Home Assistant MQTT discovery/state.

The analyzer does not write to Range Matrix SQLite. Range Matrix remains the canonical shot store; this service only contributes swing-analysis entities through MQTT.

## Architecture

```text
Nova -> OBS Open Golf Coach plugin -> MQTT topic golf/shot/raw
                                      |
                                      +-> Range Matrix HACS integration
                                      |
                                      +-> Golf Swing Analyzer service
                                             +-> OBS SaveReplayBuffer
                                             +-> MediaPipe pose + heuristics
                                             +-> annotated H.264 MP4 at 0.5x
                                             +-> HTTP video server on port 8765
                                             +-> MQTT discovery + latest analysis
```

## MQTT Contract

Subscribed topics:

- `golf/shot/raw`: shot JSON from the OBS Open Golf Coach plugin.
- `golf/swing/analyzer/enabled`: retained `on`/`off` switch state.
- `golf/context/current`: retained JSON like `{ "player": "...", "club": "...", "session_id": "..." }`. This context overrides the OBS-supplied club so the dashboard selection wins.

Published topics:

- `golf/swing/analysis/availability`: retained `online`/`offline`.
- `golf/swing/analysis/latest`: retained JSON for the latest analyzed swing.
- `golf/swing/analysis/recent`: retained JSON list of the last 5 swings.
- Home Assistant MQTT discovery under `homeassistant/switch/golf_swing_analyzer/enabled/config` and `homeassistant/sensor/golf_swing_analyzer/<id>/config`.

Home Assistant creates a `Golf Swing Analyzer` MQTT device with `switch.swing_analyzer` and the latest swing sensors.

## Install On The Sim PC

Install Python 3.11 or 3.12. MediaPipe does not support Python 3.13 yet.

```powershell
cd C:\Users\igotd\golf_swing_analyzer
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy config.example.yaml config.yaml
```

Edit `config.yaml`:

- Set `server.public_base_url` to the sim PC URL, for example `http://192.168.68.150:8765`.
- Set `mqtt.host`, `mqtt.username`, and `mqtt.password`. The current setup uses the Home Assistant user `mqtt_swing`.
- Set `obs.port` and `obs.password` to match OBS WebSocket.
- Leave `annotation.slow_motion_factor: 0.5` for half-speed annotated output, or adjust it as needed.

Do not commit the real `config.yaml`.

## OBS Setup

In OBS Studio:

1. Go to `Settings` > `Output` and switch `Output Mode` to `Advanced`.
2. Open the `Replay Buffer` tab and enable `Enable Replay Buffer`.
3. Set `Maximum Replay Time` to about `30s`.
4. Set the recording path to `C:\golf_swings\raw\`.
5. Go to `Tools` > `WebSocket Server Settings`, enable the server, and note the port/password.
6. Click `Start Replay Buffer` in the OBS Controls dock.

The replay buffer must be started, not just enabled, or `SaveReplayBuffer` will not produce a source MP4.

The Open Golf Coach OBS script publishes shots to MQTT with `paho-mqtt`. If OBS Python does not have it yet, install it into OBS's package path:

```powershell
py -3.12 -m pip install --target "$env:APPDATA\obs-studio\ogc-python\Lib\site-packages" paho-mqtt
```

## Run

```powershell
cd C:\Users\igotd\golf_swing_analyzer
.\.venv\Scripts\Activate.ps1
python run.py
```

Expected log lines include:

```text
MQTT bridge authenticated as mqtt_swing
MQTT subscribed to shot=golf/shot/raw context=golf/context/current enable=golf/swing/analyzer/enabled
```

The service serves generated videos at `http://<sim-pc-ip>:8765/videos/...`.

## Home Assistant Dashboard

The analyzer publishes MQTT discovery automatically. In Home Assistant, check `Settings` > `Devices & services` > `MQTT` for the `Golf Swing Analyzer` device.

Add `ha_dashboard_swing.yaml` as a Lovelace view, or use the bundled Range Matrix dashboard template in this repo. The video card uses Piotr Machowski's HACS `HTML Template Card`:

```yaml
url: /hacsfiles/html-template-card/html-template-card.js
type: module
```

## Smoke Test

1. Start the analyzer and confirm MQTT authentication/subscriptions in the log.
2. In Home Assistant, turn `switch.swing_analyzer` on.
3. Hit one shot.
4. Within about 30 seconds, `sensor.last_swing_annotated_url` should populate and the dashboard video should autoplay the slow-motion annotated swing.

## Retention

The analyzer keeps the latest 5 swings by default. Older raw videos, annotated videos, and analysis JSON files are removed automatically according to `retention.keep_recent_swings`.

