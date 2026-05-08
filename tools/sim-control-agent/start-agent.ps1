$ErrorActionPreference = "Stop"

$AgentRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $AgentRoot ".venv\Scripts\python.exe"
$RunPy = Join-Path $AgentRoot "run.py"

if (-not (Test-Path $VenvPython)) {
    Write-Error "Virtual environment not found: $VenvPython. Run the install steps first."
}

if (-not (Test-Path (Join-Path $AgentRoot "config.yaml"))) {
    Write-Error "config.yaml not found. Copy config.example.yaml to config.yaml and fill it in first."
}

Set-Location $AgentRoot
& $VenvPython $RunPy
