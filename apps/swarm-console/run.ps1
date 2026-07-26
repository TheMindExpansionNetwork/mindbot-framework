# S0N1C Swarm Console launcher (Windows).  Usage:  .\run.ps1
if (-not $env:SONIC_URL) { $env:SONIC_URL = Read-Host "S0N1C endpoint URL (…/v1)" }
Write-Host "starting S0N1C Swarm Console -> http://localhost:8799"
python server.py
