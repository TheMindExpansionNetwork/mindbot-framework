#!/usr/bin/env bash
# MindBot VPS installer — Debian 13 / Ubuntu, idempotent, uv-based.
#
#   curl -fsSL https://raw.githubusercontent.com/TheMindExpansionNetwork/mindbot-framework/main/vps-install.sh | bash
#
# (install.sh is the in-repo bootstrap for a checkout you already have. THIS one starts from
#  nothing on a fresh server and is the one to curl.)
#
# WHAT IT DOES
#   Installs uv, creates an isolated venv, installs MindBot, VERIFIES by running the real
#   audit, and prints exactly what to do next. It does NOT touch your firewall, SSH config, or
#   Docker — an installer that silently reconfigures a server is how you lose an afternoon to a
#   locked-out box. Provisioning belongs to you; this installs an application.
#
# WHY uv AND NOT pip
#   System Python on Debian 13 is externally-managed (PEP 668): `pip install` either refuses or
#   half-succeeds and breaks apt. uv builds a real venv in one step, resolves ~10x faster, and
#   pins a Python version independent of whatever the distro shipped. On a 6-vCPU box that is
#   minutes per rebuild.
#
# SAFE TO RE-RUN. Every step checks before acting, and it never overwrites your .env.

set -euo pipefail

REPO="${MINDBOT_REPO:-https://github.com/TheMindExpansionNetwork/mindbot-framework}"
DIR="${MINDBOT_DIR:-$HOME/mindbot}"
PY="${MINDBOT_PYTHON:-3.12}"

c_ok=$'\033[38;5;48m'; c_dim=$'\033[2m'; c_hi=$'\033[38;5;50m'; c_warn=$'\033[38;5;214m'; c_r=$'\033[0m'
say()  { printf '  %s\n' "$*"; }
ok()   { printf '  %s✓%s %s\n' "$c_ok" "$c_r" "$*"; }
warn() { printf '  %s!%s %s\n' "$c_warn" "$c_r" "$*"; }
die()  { printf '\n  %sinstall failed:%s %s\n\n' "$c_warn" "$c_r" "$*" >&2; exit 1; }

printf '\n  %s🌒 MindBot%s  VPS installer\n\n' "$c_hi" "$c_r"

# ── 1. prerequisites ─────────────────────────────────────────────────────────
# git + curl only. Deliberately NOT installing docker/n8n/postgres: those are the server's
# provisioning, and bundling them would make this unrunnable on a laptop or in CI.
if command -v apt-get >/dev/null 2>&1; then
  MISSING=()
  for p in git curl ca-certificates; do
    dpkg -s "$p" >/dev/null 2>&1 || MISSING+=("$p")
  done
  if [ ${#MISSING[@]} -gt 0 ]; then
    say "installing: ${MISSING[*]}"
    sudo apt-get update -qq && sudo apt-get install -y -qq "${MISSING[@]}" || die "apt install failed"
  fi
fi
command -v git >/dev/null 2>&1 || die "git not found and could not be installed"
ok "prerequisites"

# ffmpeg is OPTIONAL — only `mindbot watch` (video review) needs it. A missing optional
# dependency must not fail an install; most users never touch video.
if command -v ffmpeg >/dev/null 2>&1; then
  ok "ffmpeg present — 'mindbot watch' available"
else
  warn "no ffmpeg — all good except 'mindbot watch'   (sudo apt install ffmpeg)"
fi

# ── 2. uv ────────────────────────────────────────────────────────────────────
if ! command -v uv >/dev/null 2>&1; then
  say "installing uv…"
  curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 || die "uv install failed"
  export PATH="$HOME/.local/bin:$PATH"   # its installer writes here, not on a non-login PATH
fi
command -v uv >/dev/null 2>&1 || die "uv installed but not on PATH — add \$HOME/.local/bin"
ok "uv $(uv --version 2>/dev/null | awk '{print $2}')"

# ── 3. source ────────────────────────────────────────────────────────────────
if [ -d "$DIR/.git" ]; then
  say "updating $DIR"
  git -C "$DIR" pull --ff-only -q || warn "pull skipped (local changes) — using existing checkout"
else
  say "cloning into $DIR"
  git clone -q --depth 1 "$REPO" "$DIR" || die "clone failed — is $REPO reachable?"
fi
ok "source at $DIR"

# ── 4. venv + install ────────────────────────────────────────────────────────
cd "$DIR/framework" || die "no framework/ directory in $DIR"
uv venv --python "$PY" .venv >/dev/null 2>&1 || uv venv .venv >/dev/null 2>&1 || die "venv failed"
# shellcheck disable=SC1091
source .venv/bin/activate
uv pip install -q -e . || die "install failed"
ok "installed into $DIR/framework/.venv"

# ── 5. PATH shim ─────────────────────────────────────────────────────────────
# A wrapper beats telling people to activate a venv first — and it is what makes `mindbot`
# work from cron and systemd without any activation at all.
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/mindbot" <<EOF
#!/usr/bin/env bash
exec "$DIR/framework/.venv/bin/mindbot" "\$@"
EOF
chmod +x "$HOME/.local/bin/mindbot"
case ":$PATH:" in
  *":$HOME/.local/bin:"*) : ;;
  *) for rc in "$HOME/.bashrc" "$HOME/.profile"; do
       [ -f "$rc" ] && ! grep -q '.local/bin' "$rc" && \
         echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$rc"
     done
     warn "added ~/.local/bin to PATH — run: source ~/.bashrc" ;;
esac
ok "mindbot on PATH"

# ── 6. config ────────────────────────────────────────────────────────────────
# NEVER clobber an existing .env — on a re-run that silently destroys working credentials.
if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env && chmod 600 .env
  ok "created framework/.env from the example (chmod 600)"
elif [ -f .env ]; then
  ok "kept your existing framework/.env"
fi

# ── 7. verify ────────────────────────────────────────────────────────────────
# Prove the install instead of assuming it. Same audit CI runs on 12 platform/version combos.
printf '\n  %sverifying…%s\n' "$c_dim" "$c_r"
if python _full_audit.py >/tmp/mindbot_audit.log 2>&1; then
  ok "$(grep -oE 'RESULT: [0-9]+ passed, [0-9]+ failed' /tmp/mindbot_audit.log | tail -1)"
else
  warn "audit reported problems — see /tmp/mindbot_audit.log"
  grep -E '^\s+FAIL' /tmp/mindbot_audit.log | head -5 || true
fi

# ── 8. what next ─────────────────────────────────────────────────────────────
cat <<EOF

  ${c_hi}installed.${c_r}  ${c_dim}$DIR${c_r}

  ${c_dim}1. add a model — you need at least one:${c_r}
     nano $DIR/framework/.env
       OPENROUTER_API_KEY=sk-or-v1-...     ${c_dim}# text, metered${c_r}
       MODAL_ENDPOINT_URL=https://.../v1   ${c_dim}# + vision + audio, self-hosted${c_r}
       MODAL_PROXY_TOKEN_ID=wk-...         ${c_dim}# NOT ak- — that is a CLI token${c_r}
       MODAL_PROXY_TOKEN_SECRET=ws-...
       MINDBOT_MODAL=1

  ${c_dim}2. check it:${c_r}
     mindbot doctor          ${c_dim}# environment${c_r}
     mindbot modal check     ${c_dim}# endpoint, and WHICH layer failed if not${c_r}
     mindbot whoami          ${c_dim}# what it is, and what it cannot do${c_r}

  ${c_dim}3. do something:${c_r}
     mindbot studio "a script that rotates my logs"
     mindbot observe ./photos
     mindbot attest

  ${c_dim}unattended:${c_r} docs/THE_OFFICE.md   ${c_dim}·  for an AI:${c_r} AGENTS.md
  ${c_dim}nothing sends without you. drafts land in framework/outbox/.${c_r}

EOF
