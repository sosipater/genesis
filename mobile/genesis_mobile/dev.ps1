param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("get", "run", "test", "analyze", "check", "clean", "doctor")]
    [string]$Action
)

$ErrorActionPreference = "Stop"

# Always run from this Flutter project directory.
Set-Location -Path $PSScriptRoot

switch ($Action) {
    "get" {
        flutter pub get
    }
    "run" {
        flutter run
    }
    "test" {
        flutter test
    }
    "analyze" {
        flutter analyze
    }
    "check" {
        flutter analyze
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        flutter test
    }
    "clean" {
        flutter clean
        flutter pub get
    }
    "doctor" {
        flutter doctor -v
    }
}
