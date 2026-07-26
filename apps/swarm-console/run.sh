#!/usr/bin/env bash
# S0N1C Swarm Console launcher (mac/linux).  Usage:  ./run.sh
set -e
: "${SONIC_URL:?set SONIC_URL to your S0N1C endpoint (…/v1), e.g. export SONIC_URL=https://...modal.run/v1}"
echo "starting S0N1C Swarm Console -> http://localhost:${PORT:-8799}"
python3 server.py
