param(
    [string]$TaskName = "DongchediDailyChargingHealthcheck",
    [string]$Time = "10:00",
    [string]$RetryTime = "11:00",
    [string]$WorkspacePath = "c:\Users\Q653867\OneDrive - BMW Group\Desktop\V\vikipedia-agents"
)

$healthcheckScriptPath = Join-Path $WorkspacePath "scripts\run_dongchedi_daily_healthcheck.ps1"
if (-not (Test-Path $healthcheckScriptPath)) {
    throw "Healthcheck script not found: $healthcheckScriptPath"
}

$taskArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$healthcheckScriptPath`" -WorkspacePath `"$WorkspacePath`""

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $taskArgs -WorkingDirectory $WorkspacePath
$triggerPrimary = New-ScheduledTaskTrigger -Daily -At $Time
$triggerRetry = New-ScheduledTaskTrigger -Daily -At $RetryTime
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -WakeToRun -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 15)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($triggerPrimary, $triggerRetry) -Settings $settings -Force | Out-Null

Write-Host "Scheduled task created/updated: $TaskName at $Time and retry at $RetryTime"
Write-Host "Pipeline: verify today's charging artifacts; auto-recover if missing"
