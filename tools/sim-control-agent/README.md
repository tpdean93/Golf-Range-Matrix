# SIM Control Agent

Local Windows control agent for the simulator PC. It listens for fixed MQTT commands from Home Assistant and exposes buttons through MQTT discovery.

Use it when the OBS Open Golf Coach script stops publishing shots or OBS Replay Buffer needs to be restarted without logging into the sim PC.

## What It Controls

- Restart OBS Studio.
- Start OBS Studio if it is not running.
- Start OBS Replay Buffer through OBS WebSocket.
- Save OBS Replay Buffer through OBS WebSocket.
- Optionally run configured commands to restart the Swing Analyzer.

The agent does not accept arbitrary shell commands over MQTT. MQTT payloads map to known command names only.

## Install On The SIM PC

```powershell
cd C:\golf-range-matrix\tools\sim-control-agent
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item config.example.yaml config.yaml
notepad config.yaml
python run.py
```

Set `mqtt.host`, `mqtt.username`, and `mqtt.password` to the same broker/user used by the Swing Analyzer. Set `obs.websocket.password` if OBS WebSocket requires one.

## Home Assistant Entities

When the agent connects, MQTT discovery creates a device named `Golf SIM Control` with buttons similar to:

- `button.golf_sim_control_restart_obs_bridge`
- `button.golf_sim_control_start_obs`
- `button.golf_sim_control_start_replay_buffer`
- `button.golf_sim_control_save_replay_buffer`
- `button.golf_sim_control_restart_swing_analyzer`
- `sensor.golf_sim_control_status`
- `sensor.golf_sim_control_last_command`

Entity IDs may vary slightly depending on Home Assistant naming.

## MQTT Topics

Default topics:

- Command: `golf/sim/control/command`
- Status: `golf/sim/control/status`
- Availability: `golf/sim/control/availability`

Supported command payloads:

- `restart_obs`
- `start_obs`
- `start_replay_buffer`
- `save_replay_buffer`
- `restart_analyzer`

## Notes

Restarting OBS is intentionally blunt because OBS does not expose a reliable WebSocket command to reload one Python script. After OBS restarts, press `Start Replay Buffer` if your OBS setup does not start it automatically.

For automatic startup, create a Windows Scheduled Task that runs `python run.py` at logon from this folder.
