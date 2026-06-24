param(
    [string]$TaskName = "TokenGitHubDailySync",
    [string]$RunTime = "21:40",
    [string]$RetryTime = "22:10",
    [string]$WorkspacePath = "c:\Users\Q653867\OneDrive - BMW Group\Desktop\V\vikipedia-agents",
    [string]$Username = "ttoriaa",
    [int]$Limit = 12,
    [int]$TopSkills = 12,
    [int]$RecentLimit = 15,
    [int]$ProjectBoardLimit = 20,
    [switch]$IncludeHomepageAnyDomain,
    [switch]$IncludeProjectBoards
)

$runnerScriptPath = Join-Path $WorkspacePath "scripts\run_token_github_daily_task_runner.ps1"

if (-not (Test-Path $runnerScriptPath)) {
    throw "Runner script not found: $runnerScriptPath"
}

$commonArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$runnerScriptPath`" -WorkspacePath `"$WorkspacePath`" -Username `"$Username`" -Limit $Limit -TopSkills $TopSkills -RecentLimit $RecentLimit -ProjectBoardLimit $ProjectBoardLimit"

if ($IncludeHomepageAnyDomain) {
    $commonArgs = "$commonArgs -IncludeHomepageAnyDomain"
}
if ($IncludeProjectBoards) {
    $commonArgs = "$commonArgs -IncludeProjectBoards"
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "$commonArgs -Mode run" -WorkingDirectory $WorkspacePath
$triggerPrimary = New-ScheduledTaskTrigger -Daily -At $RunTime
$triggerRetry = New-ScheduledTaskTrigger -Daily -At $RetryTime

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -WakeToRun -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 15)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($triggerPrimary, $triggerRetry) -Settings $settings -Force | Out-Null

Write-Host "Scheduled task created/updated: $TaskName at $RunTime (retry at $RetryTime)"
Write-Host "Runner: $runnerScriptPath"
Write-Host "Username: $Username | Limit: $Limit | TopSkills: $TopSkills | RecentLimit: $RecentLimit"
if ($IncludeHomepageAnyDomain) {
    Write-Host "IncludeHomepageAnyDomain: true"
}
if ($IncludeProjectBoards) {
    Write-Host "IncludeProjectBoards: true (requires token for board query)"
}
