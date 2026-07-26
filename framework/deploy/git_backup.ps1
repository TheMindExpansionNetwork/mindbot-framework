# MindBot self-clone / backup — the hive commits its own state.
# Run manually or from a scheduled task. PUSH requires a human-configured remote:
# the system never creates external accounts or transmits on its own.
#   git remote add origin <your repo url>   ← the human does this, once.
$root = "Z:\MindBot_Architect_Synergetic_Cognition"
Set-Location $root
if (-not (Test-Path "$root\.git")) { git init; git branch -M main }
git add -A
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm"
git commit -m "hive backup $stamp — pulses, handoffs, ledger, artifacts" --allow-empty
# Push only if the human configured a remote (constitution: human enables transmission).
$remote = git remote 2>$null
if ($remote) {
    git push -u origin main
    Write-Host "pushed to $(git remote get-url origin) — forks welcome."
} else {
    Write-Host "local commit done. No remote configured — add one to enable cloud backup/forking."
}
