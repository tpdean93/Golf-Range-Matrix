$ErrorActionPreference = "Stop"

$TaskName = "Golf SIM Control Agent"
$AgentRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Pythonw = Join-Path $AgentRoot ".venv\Scripts\pythonw.exe"
$RunPy = Join-Path $AgentRoot "run.py"

if (-not (Test-Path $Pythonw)) {
    Write-Error "No-console Python not found: $Pythonw. Run the install steps first."
}

if (-not (Test-Path (Join-Path $AgentRoot "config.yaml"))) {
    Write-Error "config.yaml not found. Copy config.example.yaml to config.yaml and fill it in first."
}

$Action = New-ScheduledTaskAction `
    -Execute $Pythonw `
    -Argument "`"$RunPy`"" `
    -WorkingDirectory $AgentRoot

$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Days 30) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Starts the Golf SIM Control Agent for Home Assistant MQTT recovery buttons." `
    -Force | Out-Null

Write-Host "Installed scheduled task: $TaskName"
Write-Host "Starting it now..."
Start-ScheduledTask -TaskName $TaskName
Write-Host "Done. Check Task Scheduler or Home Assistant MQTT device status to confirm it is online."
