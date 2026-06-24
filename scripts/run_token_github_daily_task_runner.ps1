param(
    [string]$WorkspacePath = "c:\Users\Q653867\OneDrive - BMW Group\Desktop\V\vikipedia-agents",
    [ValidateSet("dry-run", "run")]
    [string]$Mode = "run",
    [string]$Username = "ttoriaa",
    [int]$Limit = 12,
    [int]$TopSkills = 12,
    [int]$RecentLimit = 15,
    [int]$ProjectBoardLimit = 20,
    [switch]$IncludeHomepageAnyDomain,
    [switch]$IncludeProjectBoards,
    [int]$TaskTimeoutSec = 900
)

$ErrorActionPreference = "Continue"
$PSNativeCommandUseErrorActionPreference = $false

Set-Location $WorkspacePath

$pythonPath = Join-Path $WorkspacePath ".venv\Scripts\python.exe"
$scriptPath = Join-Path $WorkspacePath "scripts\run_token_github_daily_sync.py"

if (-not (Test-Path $pythonPath)) {
    throw "Python not found: $pythonPath"
}

if (-not (Test-Path $scriptPath)) {
    throw "Script not found: $scriptPath"
}

$logDir = Join-Path $WorkspacePath "reports\task_logs"
if (-not (Test-Path $logDir)) {
    New-Item -Path $logDir -ItemType Directory -Force | Out-Null
}

$stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$logPath = Join-Path $logDir ("token_github_daily_task_{0}.log" -f $stamp)
$lockPath = Join-Path $logDir "token_github_daily_task.lock"
$outTmp = Join-Path $logDir ("token_github_daily_stdout_{0}.tmp" -f ([guid]::NewGuid().ToString("N")))
$errTmp = Join-Path $logDir ("token_github_daily_stderr_{0}.tmp" -f ([guid]::NewGuid().ToString("N")))

function Add-TempOutput {
    param(
        [string]$StdoutPath,
        [string]$StderrPath,
        [string]$TargetLogPath
    )
    if (Test-Path $StdoutPath) {
        Get-Content $StdoutPath | Out-File -FilePath $TargetLogPath -Encoding UTF8 -Append
        Remove-Item $StdoutPath -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path $StderrPath) {
        Get-Content $StderrPath | Out-File -FilePath $TargetLogPath -Encoding UTF8 -Append
        Remove-Item $StderrPath -Force -ErrorAction SilentlyContinue
    }
}

try {
    $lockStream = New-Object System.IO.FileStream($lockPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
}
catch {
    "[$(Get-Date -Format s)] SKIP token github daily task because another instance is running" | Out-File -FilePath $logPath -Encoding UTF8 -Append
    exit 0
}

"[$(Get-Date -Format s)] START token github daily task mode=$Mode username=$Username limit=$Limit top_skills=$TopSkills recent_limit=$RecentLimit" | Out-File -FilePath $logPath -Encoding UTF8 -Append

try {
    $effectiveLimit = if ($Mode -eq "dry-run") { [Math]::Min($Limit, 8) } else { $Limit }
    $effectiveTopSkills = if ($Mode -eq "dry-run") { [Math]::Min($TopSkills, 8) } else { $TopSkills }
    $effectiveRecentLimit = if ($Mode -eq "dry-run") { [Math]::Min($RecentLimit, 8) } else { $RecentLimit }

    $argList = @(
        ('"{0}"' -f $scriptPath),
        "--username", ('"{0}"' -f $Username),
        "--limit", [string]$effectiveLimit,
        "--top-skills", [string]$effectiveTopSkills,
        "--recent-limit", [string]$effectiveRecentLimit,
        "--project-board-limit", [string]$ProjectBoardLimit
    )

    if ($IncludeHomepageAnyDomain) {
        $argList += "--include-homepage-any-domain"
    }
    if ($IncludeProjectBoards) {
        $argList += "--include-project-boards"
    }

    $proc = Start-Process -FilePath $pythonPath -ArgumentList ($argList -join " ") -PassThru -NoNewWindow -RedirectStandardOutput $outTmp -RedirectStandardError $errTmp
    $finished = $proc.WaitForExit($TaskTimeoutSec * 1000)

    if (-not $finished) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        Add-TempOutput -StdoutPath $outTmp -StderrPath $errTmp -TargetLogPath $logPath
        "[$(Get-Date -Format s)] FAIL token github daily task timeout after ${TaskTimeoutSec}s" | Out-File -FilePath $logPath -Encoding UTF8 -Append
        exit 124
    }

    Add-TempOutput -StdoutPath $outTmp -StderrPath $errTmp -TargetLogPath $logPath
    $exitCode = [int]$proc.ExitCode
    if ($exitCode -ne 0) {
        "[$(Get-Date -Format s)] FAIL token github daily task exit=$exitCode" | Out-File -FilePath $logPath -Encoding UTF8 -Append
        exit $exitCode
    }

    "[$(Get-Date -Format s)] DONE token github daily task" | Out-File -FilePath $logPath -Encoding UTF8 -Append
    exit 0
}
finally {
    if (Test-Path $outTmp) {
        Remove-Item $outTmp -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path $errTmp) {
        Remove-Item $errTmp -Force -ErrorAction SilentlyContinue
    }
    if ($lockStream) {
        $lockStream.Close()
        $lockStream.Dispose()
    }
    if (Test-Path $lockPath) {
        Remove-Item $lockPath -Force -ErrorAction SilentlyContinue
    }
}
