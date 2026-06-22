param(
    [string]$TaskName = "DongchediDailyChargingReport",
    [string]$Time = "09:00",
    [string]$RetryTime = "09:10",
    [string]$FallbackTime = "09:30",
    [string]$WorkspacePath = "c:\Users\Q653867\OneDrive - BMW Group\Desktop\V\vikipedia-agents"
)

$pythonPath = Join-Path $WorkspacePath ".venv\Scripts\python.exe"
$generateScriptPath = Join-Path $WorkspacePath "scripts\run_dongchedi_daily.py"
$publishScriptPath = Join-Path $WorkspacePath "scripts\push_dongchedi_to_confluence.py"
$runnerScriptPath = Join-Path $WorkspacePath "scripts\run_dongchedi_daily_task_runner.ps1"

if (-not (Test-Path $pythonPath)) {
    throw "Python not found: $pythonPath"
}

if (-not (Test-Path $generateScriptPath)) {
    throw "Generate script not found: $generateScriptPath"
}

if (-not (Test-Path $publishScriptPath)) {
    throw "Publish script not found: $publishScriptPath"
}

if (-not (Test-Path $runnerScriptPath)) {
    throw "Runner script not found: $runnerScriptPath"
}

$taskArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$runnerScriptPath`" -WorkspacePath `"$WorkspacePath`""

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $taskArgs -WorkingDirectory $WorkspacePath
$triggerPrimary = New-ScheduledTaskTrigger -Daily -At $Time
$triggerRetry = New-ScheduledTaskTrigger -Daily -At $RetryTime
$triggerFallback = New-ScheduledTaskTrigger -Daily -At $FallbackTime
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -WakeToRun -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 15)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($triggerPrimary, $triggerRetry, $triggerFallback) -Settings $settings -Force | Out-Null

Write-Host "Scheduled task created/updated: $TaskName at $Time, retry at $RetryTime, fallback at $FallbackTime"
Write-Host "Pipeline: generate daily artifacts, then publish to Confluence"
