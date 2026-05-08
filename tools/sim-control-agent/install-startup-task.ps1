$ErrorActionPreference = "Stop"

$TaskName = "Golf SIM Control Agent"
$AgentRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$StartScript = Join-Path $AgentRoot "start-agent.ps1"

if (-not (Test-Path $StartScript)) {
    Write-Error "Start script not found: $StartScript"
}

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$StartScript`"" `
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
