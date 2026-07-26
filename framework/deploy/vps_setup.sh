#!/usr/bin/env bash
# MindBot VPS bootstrap — 10 minutes, like the HQ README promised.
# Usage: bash vps_setup.sh  (on the VPS, as the deploy user)
set -euo pipefail

DEST=/opt/mindbot
sudo mkdir -p "$DEST" && sudo chown "$(whoami)" "$DEST"

# 1. Sync the workspace (rsync from the studio machine, or git pull if the repo is remote).
#    rsync -av --exclude venv --exclude '*.zip' mindexpander@studio:/z/MindBot_Architect_Synergetic_Cognition/ $DEST/
echo "[1/4] workspace expected at $DEST (sync it; large media can stay home — the pipeline only needs text/code)"

# 2. Python 3.10+ stdlib-only — no pip, no venv, it just runs.
python3 -c 'import sys; assert sys.version_info >= (3,10), "need python3.10+"'
echo "[2/4] python ok"

# 3. API keys for the counselors' big models (only the ones you have; everything degrades gracefully).
#    Add to ~/.profile:  export ANTHROPIC_API_KEY=...  OPENAI_API_KEY=...  XAI_API_KEY=...
#    DEEPSEEK_API_KEY=... GOOGLE_API_KEY=... MISTRAL_API_KEY=...  OLLAMA_HOST=...
echo "[3/4] export API keys in ~/.profile (skip any — template mode keeps the loop alive)"

# 4. Install the cron table.
crontab "$DEST/17_Framework_Pipeline/deploy/crontab.vps"
echo "[4/4] crontab installed. First pulse within 15 minutes. Report at 07:00."
echo "The loop is the magic."
