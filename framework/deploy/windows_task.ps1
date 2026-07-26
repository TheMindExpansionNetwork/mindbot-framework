# M1NDB0TZ — Windows scheduled tasks (the cron, for this machine).
# Run once in an ELEVATED PowerShell:  .\framework\deploy\windows_task.ps1
# Drafts only; the human merges staging->main. Nothing transmits.
$root = "Z:\MINDBOTZ\framework"
$py = (Get-Command python).Source

function Task($name, $cli, $trigger) {
  # Wrap in cmd.exe so each unattended run sets the COST-SAFETY env first: free models only,
  # NEVER the billed GPU fleet. An around-the-clock loop must never surprise-bill.
  $cmd = "set MINDBOT_FREE=1&& set MINDBOT_NO_SONIC=1&& `"$py`" -m mindbot_pipeline.cli $cli"
  $a = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c $cmd" -WorkingDirectory $root
  Register-ScheduledTask -TaskName $name -Action $a -Trigger $trigger -Force | Out-Null
  Write-Host "  installed: $name" -ForegroundColor Green
}

# 15-minute heartbeat
Task "MindBotz Pulse (15m)" "pulse" `
  (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 15))

# Nightly YOLO sprint (00:30)
Task "MindBotz YOLO (nightly)" "yolo --rounds 40" `
  (New-ScheduledTaskTrigger -Daily -At 12:30am)

# Dawn dream cycle (04:15)
Task "MindBotz Dream (dawn)" "pulse --agent Spark" `
  (New-ScheduledTaskTrigger -Daily -At 4:15am)

# Morning report (07:00)
Task "MindBotz Morning Report (7am)" "report" `
  (New-ScheduledTaskTrigger -Daily -At 7:00am)

Write-Host ""
Write-Host "  the hive now builds around the clock. review the 7am report, merge staging->main." -ForegroundColor Cyan
Write-Host "  remove anytime:  Get-ScheduledTask 'MindBotz *' | Unregister-ScheduledTask -Confirm:`$false" -ForegroundColor DarkGray
