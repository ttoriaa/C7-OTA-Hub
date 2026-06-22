param(
    [string]$WorkspacePath = "c:\Users\Q653867\OneDrive - BMW Group\Desktop\V\vikipedia-agents"
)

$ErrorActionPreference = "Continue"
$PSNativeCommandUseErrorActionPreference = $false

Set-Location $WorkspacePath

$reportDir = Join-Path $WorkspacePath ("reports\dongchedi_daily\{0}" -f (Get-Date -Format "yyyy-MM-dd"))
$logDir = Join-Path $WorkspacePath "reports\task_logs"
$runnerPath = Join-Path $WorkspacePath "scripts\run_dongchedi_daily_task_runner.ps1"

if (-not (Test-Path $logDir)) {
    New-Item -Path $logDir -ItemType Directory -Force | Out-Null
}

$logPath = Join-Path $logDir ("charging_healthcheck_{0}.log" -f (Get-Date -Format "yyyy-MM-dd_HHmmss"))
"[$(Get-Date -Format s)] START charging healthcheck" | Out-File -FilePath $logPath -Encoding UTF8 -Append

$expectedFiles = @(
    "filtered.csv",
    "filtered.json",
    "summary.md",
    "confluence_section.html"
)

$missing = @()
if (-not (Test-Path $reportDir)) {
    $missing += "report_dir"
}
else {
    foreach ($name in $expectedFiles) {
        $candidate = Join-Path $reportDir $name
        if (-not (Test-Path $candidate)) {
            $missing += $name
        }
    }
}

if ($missing.Count -eq 0) {
    "[$(Get-Date -Format s)] OK report already present: $reportDir" | Out-File -FilePath $logPath -Encoding UTF8 -Append
    exit 0
}

"[$(Get-Date -Format s)] MISSING artifacts: $($missing -join ', ')" | Out-File -FilePath $logPath -Encoding UTF8 -Append
"[$(Get-Date -Format s)] RECOVER run charging runner" | Out-File -FilePath $logPath -Encoding UTF8 -Append

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$runnerPath" -WorkspacePath "$WorkspacePath" *>> $logPath
$runnerExit = $LASTEXITCODE

if ($runnerExit -ne 0) {
    "[$(Get-Date -Format s)] FAIL recovery runner exit=$runnerExit" | Out-File -FilePath $logPath -Encoding UTF8 -Append
    exit $runnerExit
}

"[$(Get-Date -Format s)] DONE recovery success" | Out-File -FilePath $logPath -Encoding UTF8 -Append
exit 0
