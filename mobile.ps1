param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("get", "run", "test", "analyze", "check", "clean", "doctor")]
    [string]$Action
)

$ErrorActionPreference = "Stop"

$mobileScript = Join-Path $PSScriptRoot "mobile\genesis_mobile\dev.ps1"

if (-not (Test-Path $mobileScript)) {
    throw "Mobile helper script not found: $mobileScript"
}

& $mobileScript $Action
exit $LASTEXITCODE
