param(
    [string]$WorkspacePath = "c:\Users\Q653867\OneDrive - BMW Group\Desktop\V\vikipedia-agents",
    [int]$GenerateTimeoutSec = 240
)

$ErrorActionPreference = "Continue"
$PSNativeCommandUseErrorActionPreference = $false

Set-Location $WorkspacePath

$pythonPath = Join-Path $WorkspacePath ".venv\Scripts\python.exe"
$generateScriptPath = Join-Path $WorkspacePath "scripts\run_dongchedi_motor_daily.py"
$publishScriptPath = Join-Path $WorkspacePath "scripts\push_dongchedi_motor_to_confluence.py"

$logDir = Join-Path $WorkspacePath "reports\task_logs"
if (-not (Test-Path $logDir)) {
    New-Item -Path $logDir -ItemType Directory -Force | Out-Null
}
$logPath = Join-Path $logDir ("motor_task_{0}.log" -f (Get-Date -Format "yyyy-MM-dd_HHmmss"))
$lockPath = Join-Path $logDir "motor_task.lock"
$outTmp = Join-Path $logDir ("motor_task_stdout_{0}.tmp" -f ([guid]::NewGuid().ToString("N")))
$errTmp = Join-Path $logDir ("motor_task_stderr_{0}.tmp" -f ([guid]::NewGuid().ToString("N")))

function Append-TempOutput {
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
    "[$(Get-Date -Format s)] SKIP motor task because another instance is running" | Out-File -FilePath $logPath -Encoding UTF8 -Append
    exit 0
}

"[$(Get-Date -Format s)] START motor task" | Out-File -FilePath $logPath -Encoding UTF8 -Append

try {
    $generateArgs = @(
        ('"{0}"' -f $generateScriptPath),
        "--dry-run",
        "--enrich-timeout-sec", "5",
        "--enrich-max-series", "8"
    ) -join " "
    $generateProc = Start-Process -FilePath $pythonPath -ArgumentList $generateArgs -PassThru -NoNewWindow -RedirectStandardOutput $outTmp -RedirectStandardError $errTmp
    $finished = $generateProc.WaitForExit($GenerateTimeoutSec * 1000)
    if (-not $finished) {
        Stop-Process -Id $generateProc.Id -Force -ErrorAction SilentlyContinue
        Append-TempOutput -StdoutPath $outTmp -StderrPath $errTmp -TargetLogPath $logPath
        "[$(Get-Date -Format s)] FAIL generate timeout after ${GenerateTimeoutSec}s" | Out-File -FilePath $logPath -Encoding UTF8 -Append
        exit 124
    }
    Append-TempOutput -StdoutPath $outTmp -StderrPath $errTmp -TargetLogPath $logPath
    $generateExitCode = [int]$generateProc.ExitCode

    if ($generateExitCode -ne 0) {
        "[$(Get-Date -Format s)] FAIL generate exit=$generateExitCode" | Out-File -FilePath $logPath -Encoding UTF8 -Append
        exit $generateExitCode
    }

    $publishExitCode = 0
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        "[$(Get-Date -Format s)] publish attempt=$attempt" | Out-File -FilePath $logPath -Encoding UTF8 -Append
        & $pythonPath $publishScriptPath *>> $logPath
        $publishExitCode = $LASTEXITCODE
        if ($publishExitCode -eq 0) {
            break
        }
    }

    if ($publishExitCode -ne 0) {
        "[$(Get-Date -Format s)] WARN publish exit=$publishExitCode after retries; keep task success because local artifacts are generated" | Out-File -FilePath $logPath -Encoding UTF8 -Append
        "[$(Get-Date -Format s)] DONE motor task with publish warning" | Out-File -FilePath $logPath -Encoding UTF8 -Append
        exit 0
    }

    "[$(Get-Date -Format s)] DONE motor task" | Out-File -FilePath $logPath -Encoding UTF8 -Append
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
