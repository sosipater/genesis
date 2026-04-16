param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("run", "sync-host", "test", "backup", "validate-backup", "restore", "diagnostics", "media-scan", "release-check")]
    [string]$Action,
    [Parameter(Position = 1)]
    [string]$Path,
    [switch]$AllowReplace,
    [switch]$CleanupOrphans,
    [switch]$WithBackup,
    [switch]$WithTests,
    [switch]$VerboseReport
)

$ErrorActionPreference = "Stop"

switch ($Action) {
    "run" {
        python -m desktop.app.main --mode desktop
        exit $LASTEXITCODE
    }
    "sync-host" {
        python -m desktop.app.main --mode sync-host
        exit $LASTEXITCODE
    }
    "test" {
        python -m pytest desktop/tests -q
        exit $LASTEXITCODE
    }
    "backup" {
        if (-not $Path) { throw "Provide backup output path (.zip)." }
        python tools/ops_desktop.py backup --out "$Path"
        exit $LASTEXITCODE
    }
    "validate-backup" {
        if (-not $Path) { throw "Provide backup path (.zip)." }
        python tools/ops_desktop.py validate-backup --path "$Path"
        exit $LASTEXITCODE
    }
    "restore" {
        if (-not $Path) { throw "Provide backup path (.zip)." }
        if ($AllowReplace) {
            python tools/ops_desktop.py restore --path "$Path" --allow-replace
        }
        else {
            python tools/ops_desktop.py restore --path "$Path"
        }
        exit $LASTEXITCODE
    }
    "diagnostics" {
        python tools/ops_desktop.py diagnostics
        exit $LASTEXITCODE
    }
    "media-scan" {
        if ($CleanupOrphans) {
            python tools/ops_desktop.py media-scan --cleanup-orphans
        }
        else {
            python tools/ops_desktop.py media-scan
        }
        exit $LASTEXITCODE
    }
    "release-check" {
        $argsList = @("tools/release_readiness_report.py")
        if ($WithBackup) {
            $argsList += "--with-backup"
        }
        if ($WithTests) {
            $argsList += "--with-tests"
        }
        if ($VerboseReport) {
            $argsList += "--verbose"
        }
        python @argsList
        exit $LASTEXITCODE
    }
}
