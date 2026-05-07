# Golf Swing Analyzer

Local-only golf swing analysis pipeline that ties together:

- **OpenLaunch Nova** for club/ball metrics (already in Home Assistant via HACS)
- **OBS replay buffer** for swing video
- **MediaPipe Pose** for body tracking
- **OpenCV** for an annotated video overlay
- **Optional local LLM** (Ollama / Trinity) for a coaching summary
- **Home Assistant** for triggering and displaying everything

> The analyzer **never tries to track the clubface from video**. Nova is the source of truth for club/ball numbers; the camera is only for body mechanics.

---

## How it flows

```
Nova -> OBS Open Golf Coach plugin -> MQTT golf/shot/raw
                                      │
                                      ├─> Range Matrix HACS integration
                                      │      logs canonical shot data
                                      │
                                      └─> Golf Swing Analyzer service
                                             subscribes to enable + context
                                             tells OBS to save replay buffer
                                             runs MediaPipe pose + faults
                                             renders annotated 0.5x MP4
                                             serves MP4s on port 8765
                                             publishes MQTT discovery + analysis
```

The analyzer does not write to Range Matrix SQLite. Range Matrix remains the canonical shot store; this service only contributes swing-analysis sensors and video URLs through MQTT discovery.

---

## One-time setup on the Windows sim PC

### 1. Python

Install Python 3.11 or 3.12 (MediaPipe doesn't support 3.13 yet).

```powershell
cd C:\nova-bag-builder-shot-logger\tools\swing-analyzer
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. OBS replay buffer

In OBS Studio:

1. `Settings` > `Output` > switch `Output Mode` to `Advanced`.
2. Find the `Replay Buffer` tab.
3. Enable `Enable Replay Buffer`.
4. Set `Maximum Replay Time` to `30s` (or whatever you want).
5. Set the recording path to `C:\golf_swings\raw\`.
6. `Settings` > `Hotkeys` > set a hotkey for `Save Replay` (so you can also save manually).
7. Click the `Start Replay Buffer` button in the Controls dock.

### 3. OBS WebSocket

`Tools` > `WebSocket Server Settings`:

- Enable WebSocket Server.
- Note the `Server Port` (default `4455` in OBS 32).
- If you set a password, copy it.
- Update `obs.port` and `obs.password` in `config.yaml`.

### 4. Configure the analyzer

Copy `config.example.yaml` to `config.yaml`, then edit it:

- `mqtt.host`, `mqtt.username`, and `mqtt.password` — use the Mosquitto broker and the `mqtt_swing` Home Assistant user account.
- `mqtt.shot_topic` — defaults to `golf/shot/raw`, the same topic Range Matrix consumes.
- `mqtt.context_topic` — defaults to `golf/context/current`, where Range Matrix publishes the selected player/club/session.
- `mqtt.enable_topic` — defaults to `golf/swing/analyzer/enabled`, controlled by the MQTT discovery switch.
- `server.public_base_url` — set this to the sim PC URL, e.g. `http://192.168.68.150:8765`.
- `obs.port` and `obs.password` — match OBS WebSocket settings.
- `camera.angle` — `down_the_line` or `face_on`.
- `llm.enabled` — `true` if you have Ollama / Trinity running locally.

If the dashboard browser is not on the sim PC, allow inbound TCP `8765` through Windows Firewall. Home Assistant and kiosk clients fetch annotated MP4s directly from `server.public_base_url`.

### 5. Run the analyzer

```powershell
cd C:\nova-bag-builder-shot-logger\tools\swing-analyzer
.\.venv\Scripts\Activate.ps1
python run.py
```

You should see:

```
HTTP server on http://0.0.0.0:8765
Watching: C:\golf_swings\raw
Connected to OBS at 127.0.0.1:4455
MQTT subscribed to shot=golf/shot/raw context=golf/context/current enable=golf/swing/analyzer/enabled
```

### 6. Home Assistant side

When the service starts, MQTT discovery creates a `Golf Swing Analyzer` device. Home Assistant commonly prefixes entity IDs with the device name, so the default entities are:

- `switch.golf_swing_analyzer_swing_analyzer`
- `sensor.golf_swing_analyzer_last_swing_club`
- `sensor.golf_swing_analyzer_last_swing_player`
- `sensor.golf_swing_analyzer_last_swing_body_summary`
- `sensor.golf_swing_analyzer_last_swing_faults`
- `sensor.golf_swing_analyzer_last_swing_summary`
- `sensor.golf_swing_analyzer_last_swing_annotated_url`
- `sensor.golf_swing_analyzer_last_swing_raw_url`
- `sensor.golf_swing_analyzer_last_swing_timestamp`

Add the `ha_dashboard_swing.yaml` view to the Range Matrix dashboard, or use the bundled dashboard template in the integration. The bundled `/golf_range_matrix/golf-range-matrix-cards.js` resource includes `custom:range-swing-video-card`, which loops the latest annotated MP4 and includes a compact analyzer on/off control.

Range Matrix also publishes retained context to `golf/context/current` whenever the selected player, club, recording state, or workflow changes. The analyzer applies that context before saving shot JSON, so the annotated overlay and MQTT sensors use the club selected in the dashboard.

---

## Quick test (no Nova required)

1. Start OBS and click `Start Replay Buffer`.
2. Start the analyzer (`python run.py`).
3. In Home Assistant, turn `switch.golf_swing_analyzer_swing_analyzer` on.
4. Hit one shot so the OBS plugin publishes `golf/shot/raw`.
5. Within about 30 seconds, `sensor.golf_swing_analyzer_last_swing_annotated_url` should populate and the dashboard video should auto-play.

---

## LLM Coaching

The first-pass heuristics are intentionally conservative: they extract pose metrics, derive obvious faults, and write a short body summary. For richer feedback, enable `llm.enabled` and point `llm.endpoint` at a local model server such as Ollama:

```yaml
llm:
  enabled: true
  endpoint: "http://localhost:11434/api/generate"
  model: "trinity"
  timeout_seconds: 60
```

The LLM receives the structured analysis JSON: club, camera angle, NOVA metrics, body metrics, detected faults, and the heuristic summary. A good next iteration is to tune `llm.py` with your preferred coaching style and have it return a stricter JSON object with priorities, drills, and confidence.

Keep the deterministic heuristics as the source of truth for extracted measurements. Use the LLM to explain patterns, rank likely issues, and suggest drills rather than to invent measurements from the video.

## Camera And FPS Notes

Higher FPS should improve phase detection because impact, transition, and early extension happen quickly. After upgrading the camera:

- Keep OBS recording the camera at its real frame rate and verify the saved MP4 reports that FPS correctly.
- Set `camera.fps_sample_rate: 1` if the sim PC can handle analyzing every frame. Use `2` or higher if MediaPipe CPU/GPU load is too high.
- Keep shutter speed and lighting high enough to reduce motion blur; higher FPS alone will not help if the body landmarks smear.
- Recheck `annotation.slow_motion_factor`; 0.5x is good for review, but very high FPS clips may look better at 0.4x or 0.25x.
- Keep the down-the-line camera square to the target line before comparing swing-to-swing metrics.

---

## Files

```
golf_swing_analyzer/
├── run.py                 # entry point
├── config.yaml            # all configuration
├── requirements.txt
├── ha_dashboard_swing.yaml # Lovelace view snippet
├── README.md
└── golf_swing_analyzer/
    ├── analyzer.py        # main service: MQTT + watchdog + worker
    ├── config.py          # config loader with defaults
    ├── mqtt_bridge.py     # MQTT subscriptions, discovery, and analysis publish
    ├── obs_client.py      # OBS WebSocket SaveReplayBuffer
    ├── pose.py            # MediaPipe pose extraction
    ├── metrics.py         # body metrics + phase detection + faults
    ├── annotate.py        # OpenCV annotated video overlay
    └── llm.py             # optional Ollama/Trinity summary
```

---

## Limits / philosophy

- This is **MVP**. Phase detection is heuristic, not perfect.
- Numbers are **suggestions**, not coach-grade truth.
- Down-the-line camera is the recommended starting angle.
- Face-on camera works but some metrics (early extension, hip sway) are tuned for DTL.
- Everything runs locally. No cloud calls unless you point `llm.endpoint` at one.

