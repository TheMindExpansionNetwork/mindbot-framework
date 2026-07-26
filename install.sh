#!/usr/bin/env bash
# M1NDB0TZ installer — Linux / macOS / WSL / Raspberry Pi. Stdlib-only core: no pip needed.
set -euo pipefail
cd "$(dirname "$0")"
echo ""
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║   M1NDB0TZ — a collective that dreams in public ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""
PY=$(command -v python3 || command -v python || true)
[ -z "$PY" ] && { echo "  ✗ need Python 3.10+ — install it, then re-run."; exit 1; }
"$PY" -c 'import sys; raise SystemExit(0 if sys.version_info>=(3,10) else 1)' \
  || { echo "  ✗ Python 3.10+ required."; exit 1; }
echo "  ✓ $($PY --version)"

# optional .env for model keys (the core runs without one)
if [ ! -f framework/.env ]; then
  printf 'OPENROUTER_API_KEY=\n# MINDBOT_FREE=1\n' > framework/.env
  echo "  • wrote framework/.env  (add your OPENROUTER_API_KEY — or leave blank, free models work)"
fi

# PRIMARY: editable install -> a real `mindbot` command on PATH (no third-party deps pulled).
if "$PY" -m pip install -e ./framework --quiet 2>/dev/null; then
  echo "  ✓ installed 'mindbot' command (pip -e ./framework)"
else
  # FALLBACK (no pip / locked env): a tiny launcher shim on PATH.
  echo "  • pip unavailable — writing a launcher shim instead"
  LAUNCH="$HOME/.local/bin/mindbot"
  mkdir -p "$HOME/.local/bin" 2>/dev/null || true
  cat > "$LAUNCH" <<EOF || true
#!/usr/bin/env bash
cd "$(pwd)/framework" && exec $PY -m mindbot_pipeline.cli "\$@"
EOF
  chmod +x "$LAUNCH" 2>/dev/null || true
fi

echo "  ✓ installed."
echo ""
echo "  next:"
echo "    mindbot doctor        # verify your setup"
echo "    mindbot build-agent   # forge your agent"
echo "    mindbot play          # the switchboard"
echo "  (if 'mindbot' isn't found, ensure pip's bin dir / ~/.local/bin is on PATH,"
echo "   or run:  cd framework && $PY -m mindbot_pipeline.cli doctor )"
echo ""
echo "  the loop is the magic. 🌒"
