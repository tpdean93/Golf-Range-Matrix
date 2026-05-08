$ErrorActionPreference = "Stop"

$TaskName = "Golf Swing Analyzer"
$AgentRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$StartScript = Join-Path $AgentRoot "start-agent.ps1"

if (-not (Test-Path $StartScript)) {
    Write-Error "Start script not found: $StartScript"
}

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$StartScript`"" `
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
    -Description "Starts the Golf Swing Analyzer for MQTT-driven OBS replay analysis." `
    -Force | Out-Null

Write-Host "Installed scheduled task: $TaskName"
Write-Host "Starting it now..."
Start-ScheduledTask -TaskName $TaskName
Write-Host "Done. Check Task Scheduler or the Golf Swing Analyzer MQTT device status to confirm it is online."
