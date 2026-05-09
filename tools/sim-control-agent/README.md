# SIM Control Agent

Local Windows control agent for the simulator PC. It listens for fixed MQTT commands from Home Assistant and exposes buttons through MQTT discovery.

Use it when the OBS Open Golf Coach script stops publishing shots or OBS Replay Buffer needs to be restarted without logging into the sim PC.

## What It Controls

- Restart OBS Studio.
- Start OBS Studio if it is not running.
- Select the configured Swing Analyzer OBS scene.
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
.\start-agent.ps1
```

Set `mqtt.host`, `mqtt.username`, and `mqtt.password` to the same broker/user used by the Swing Analyzer. Set `obs.websocket.password` if OBS WebSocket requires one.

Set `obs.swing_analyzer_scene` to the exact OBS scene name that should be active for swing capture. For your current setup, that is likely:

```yaml
obs:
  swing_analyzer_scene: "Swing Analyzer"
```

## Home Assistant Entities

When the agent connects, MQTT discovery creates a device named `Golf SIM Control` with buttons similar to:

- `button.golf_sim_control_restart_obs_bridge`
- `button.golf_sim_control_start_obs`
- `button.golf_sim_control_select_swing_analyzer_scene`
- `button.golf_sim_control_start_replay_buffer`
- `button.golf_sim_control_save_replay_buffer`
- `button.golf_sim_control_restart_swing_analyzer`
- `sensor.golf_sim_control_status`
- `sensor.golf_sim_control_last_command`
- `sensor.golf_sim_control_obs_scene`
- `sensor.golf_sim_control_scene_matches`

Entity IDs may vary slightly depending on Home Assistant naming.

## Start Automatically

After the agent works manually, install the startup task:

```powershell
cd C:\golf-range-matrix\tools\sim-control-agent
.\install-startup-task.ps1
```

That creates a Windows Scheduled Task named `Golf SIM Control Agent`, starts it immediately, and starts it again whenever you log into the SIM PC. The scheduled task runs `.venv\Scripts\pythonw.exe`, so it runs in the background without a console window.

To remove the task:

```powershell
.\uninstall-startup-task.ps1
```

For manual debugging with visible logs, right-click `start-agent.ps1` and choose `Run with PowerShell`, or create a desktop shortcut to:

```text
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\golf-range-matrix\tools\sim-control-agent\start-agent.ps1"
```

## MQTT Topics

Default topics:

- Command: `golf/sim/control/command`
- Status: `golf/sim/control/status`
- Availability: `golf/sim/control/availability`

Supported command payloads:

- `restart_obs`
- `start_obs`
- `select_swing_analyzer_scene`
- `start_replay_buffer`
- `save_replay_buffer`
- `restart_analyzer`

## Notes

Restarting OBS is intentionally blunt because OBS does not expose a reliable WebSocket command to reload one Python script. After OBS restarts, press `Start Replay Buffer` if your OBS setup does not start it automatically.

`Start Replay Buffer` is idempotent. If the buffer is already running, the agent reports OK without erroring. `Save Replay Buffer` requires the buffer to be running and reports a clear `Replay buffer is not running` message otherwise.

Use `Select Swing Analyzer Scene` before practice if GSPro or OBS scene changes leave the wrong scene active. `sensor.golf_sim_control_scene_matches` reports whether the current OBS scene matches `obs.swing_analyzer_scene`.

Use `install-startup-task.ps1` for automatic startup instead of manually navigating to this folder after every reboot.

## Archive Saved Replays To Home Assistant

When `archive.enabled: true`, every successful `save_replay_buffer` copies the new clip to a folder Home Assistant exposes through Media Browser. Anything in HA's Media Browser is reachable through Nabu Casa, so the latest replays stay playable when you are off your home Wi-Fi.

### One-time setup on Home Assistant OS

1. Settings -> Add-ons -> Add-on Store -> install and start `Samba share`.
2. In the add-on, set a username/password and start it.
3. From the SIM PC, confirm `\\homeassistant\media` is reachable in Explorer.
4. Create `\\homeassistant\media\golf_replays` once.

### Configure the agent

```yaml
archive:
  enabled: true
  destination: '\\homeassistant\media\golf_replays'
  keep_last: 5
  filename_template: "swing_{timestamp}_{original}"
```

Forward slashes work too (e.g. `H:/golf_replays`). UNC is recommended over a mapped drive because the agent runs as a scheduled task and mapped drives may not be visible in some sessions. If you must use credentials, run once on the SIM PC as the same user the task uses:

```powershell
cmdkey /add:homeassistant /user:<samba-user> /pass:<samba-password>
```

### What the agent does after each save

1. Calls `SaveReplayBuffer` and waits up to a few seconds for OBS to write the file.
2. Reads the saved path from `GetLastReplayBufferReplay`.
3. Copies the file into the destination folder using `swing_<timestamp>_<original>`. The copy lands as `*.part` first, then renames to its final name, so HA never sees a half-written clip.
4. Sorts the destination folder by modified time and deletes anything beyond `keep_last`.

`sensor.golf_sim_control_last_result` reports the archive outcome (e.g. `Saved 2026-05-08 19-10-12.mp4 -> HA media as swing_20260508_191012_2026-05-08 19-10-12.mp4 (kept 5)`). If the share is unreachable, the agent still reports OK on the save itself but includes `archive skipped: ...` in the message.
