# Touchline: register the update runs in Windows Task Scheduler.
# Run once in PowerShell from the repo folder:  powershell -ExecutionPolicy Bypass -File runner\windows\install-tasks.ps1
# Re-run it any time to change the schedule (it replaces the existing tasks).
#
# Runs as you, whether or not you are signed in ("S4U", no password stored), wakes the machine if needed,
# never starts a second copy while one is still going, and stops any run after 15 minutes.
param(
  [string]$RepoDir = (Resolve-Path "$PSScriptRoot\..\..").Path,
  [string]$SundayStart = "10:00",
  [int]$SundayHours = 8,
  [int]$EveryMinutes = 10,
  [string]$SaturdayAt = "08:50",
  [string]$MondayAt = "07:50"
)
$ErrorActionPreference = "Stop"
$python = Join-Path $RepoDir ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "No Python found at $python. Follow runner\README.md step 3 first." }

$action = New-ScheduledTaskAction -Execute $python -Argument "runner\touchline.py run" -WorkingDirectory $RepoDir
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -MultipleInstances IgnoreNew `
  -ExecutionTimeLimit (New-TimeSpan -Minutes 15) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -RestartCount 0

# Sunday: every N minutes from the start time for the window (finishing on the hour)
$sunday = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At $SundayStart
$repeat = New-ScheduledTaskTrigger -Once -At $SundayStart -RepetitionInterval (New-TimeSpan -Minutes $EveryMinutes) `
  -RepetitionDuration (New-TimeSpan -Hours $SundayHours -Minutes 1)
$sunday.Repetition = $repeat.Repetition

$saturday = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Saturday -At $SaturdayAt
$monday = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At $MondayAt

Register-ScheduledTask -TaskPath "\Touchline\" -TaskName "Sunday match-day checks" -Action $action -Trigger $sunday `
  -Principal $principal -Settings $settings -Description "Touchline results from FA Full-Time, match-day checks" -Force | Out-Null
Register-ScheduledTask -TaskPath "\Touchline\" -TaskName "Saturday and Monday full refresh" -Action $action `
  -Trigger @($saturday, $monday) -Principal $principal -Settings $settings `
  -Description "Touchline results from FA Full-Time, full refresh" -Force | Out-Null

Get-ScheduledTask -TaskPath "\Touchline\" | ForEach-Object {
  $i = $_ | Get-ScheduledTaskInfo
  "{0,-34} next run {1}" -f $_.TaskName, $i.NextRunTime
}
"Done. To test now: Start-ScheduledTask -TaskPath '\Touchline\' -TaskName 'Saturday and Monday full refresh'"
