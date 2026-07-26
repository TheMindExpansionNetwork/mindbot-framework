"""TUI — badass unicode terminal effects. Stdlib only, zero deps, works everywhere.

Inspired by gunnargray-dev/unicode-animations: braille (2x4 dot-matrix) grids,
spinners, waves, pulses — rendered as raw frame data with ANSI color. Used by the
`play` boot sequence and the agent-working spinner. Deterministic where it matters.

Extend: add an effect -> a pure function returning text (or a list of lines); animated
effects must early-return a plain print when `_supports()` is False (no TTY) so logs
and piped output stay clean. Reuse the ANSI constants (R/B/DIM/colors) and the `_PAL`
256-color ramp rather than hardcoding escapes. New palettes -> append to `_PAL`/`GRAD`.
"""
import re
import sys
import time

# ── Windows VT enable — without this, ANSI prints as raw ←[38;5..m garbage ────
def _enable_vt():
    if sys.platform != "win32":
        return
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.SetConsoleMode(k.GetStdHandle(-11), 7)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING|...
    except Exception:
        pass
_enable_vt()

# ── ANSI ────────────────────────────────────────────────────────────────────
R = "\033[0m"; B = "\033[1m"; DIM = "\033[2m"
CYAN = "\033[38;5;50m"; VIOLET = "\033[38;5;141m"; AMBER = "\033[38;5;214m"
PINK = "\033[38;5;212m"; GREEN = "\033[38;5;48m"; BLUE = "\033[38;5;39m"
GRAD = [AMBER, "\033[38;5;215m", "\033[38;5;216m", PINK, VIOLET, "\033[38;5;99m", CYAN]

def _supports():
    try:
        return sys.stdout.isatty()
    except Exception:
        return False

# ── braille spinner ───────────────────────────────────────────────────────────
SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
WAVE = "⠁⠂⠄⡀⢀⠠⠐⠈"  # rotating single dot
DNA  = "⠋⠉⠙⠚⠒⠂⠂⠒⠲⠴⠦⠖⠒⠐⠐⠒⠓⠋"

def spinner(label, color=CYAN, frames=SPIN):
    """Return a callable step() that prints one spinner frame in place."""
    i = [0]
    def step(msg=label):
        f = frames[i[0] % len(frames)]; i[0] += 1
        sys.stdout.write(f"\r  {color}{f}{R} {DIM}{msg}{R}   ")
        sys.stdout.flush()
    return step

# ── braille grid (2 cols x 4 rows per char) ─────────────────────────────────
# dot bit map for braille: (col,row)->bit
_BITS = {(0,0):0x01,(0,1):0x02,(0,2):0x04,(1,0):0x08,(1,1):0x10,(1,2):0x20,(0,3):0x40,(1,3):0x80}
def grid_to_braille(grid):
    """grid: list of rows of 0/1. Pack into braille chars (W/2 x H/4).

    Each output char encodes a 2x4 dot cell; bit layout is non-linear (the dot-3
    row is 0x40/0x80, not sequential) — see _BITS, which is the Unicode contract.
    """
    H = len(grid); W = len(grid[0]) if H else 0
    out = []
    for cy in range(0, H, 4):
        line = ""
        for cx in range(0, W, 2):
            v = 0
            for (dx, dy), bit in _BITS.items():
                y, x = cy + dy, cx + dx
                if y < H and x < W and grid[y][x]:
                    v |= bit
            line += chr(0x2800 + v)
        out.append(line)
    return out

_RAMP = "⣀⠤⠒⠉"  # bottom→top single clean braille row
def wave_banner(width=64, t=0.0):
    """A clean flowing braille wave line — one char per column by sine height."""
    import math
    out = []
    for x in range(width):
        h = int(3 * (0.5 + 0.5 * math.sin(x * 0.3 + t)))
        out.append(_RAMP[h])
    return "".join(out)

def third_eye(open_amt, color=AMBER):
    """The third eye, opening. open_amt 0..4. The Mind, watching."""
    pupil = (" ", "·", "•", "◉", "◉")[max(0, min(4, open_amt))]
    lid = ("▔▔▔▔▔", "╴╴╴╴╴", "◜───◝", "╱   ╲", "╱   ╲")[max(0, min(4, open_amt))]
    return [f"   {DIM}{lid}{R}", f"  {color}{B}<( {pupil} )>{R}", f"   {DIM}{'▁▁▁▁▁' if open_amt>2 else '     '}{R}"]

def think(label, fn, color=CYAN):
    """Run fn() in a thread while a braille spinner animates LIVE. Returns fn()'s result.

    This is the sci-fi bit: the eye spins in real time WHILE the model thinks,
    not a fake pre-roll. Falls back to a plain print with no TTY.
    """
    import threading
    box = {}
    def run(): box["r"] = fn()
    th = threading.Thread(target=run, daemon=True); th.start()
    if not _supports():
        th.join(); return box.get("r")
    i = 0
    while th.is_alive():
        f = SPIN[i % len(SPIN)]; eye = ("◉", "◉", "◎", "●")[i % 4]
        sys.stdout.write(f"\r  {color}{f}{R} {DIM}{label}{R} {color}<( {eye} )>{R}   ")
        sys.stdout.flush(); i += 1; time.sleep(0.08)
    sys.stdout.write("\r" + " " * 60 + "\r"); sys.stdout.flush()
    return box.get("r")

def panel(title, lines, color=CYAN, width=64):
    """A boxed sci-fi panel."""
    out = [f"  {color}╔{'═'*(width-2)}╗{R}",
           f"  {color}║{R} {B}{title}{R}{' '*(width-3-len(title))}{color}║{R}",
           f"  {color}╟{'─'*(width-2)}╢{R}"]
    for ln in lines:
        # measure visible width with ANSI stripped, else color codes throw off padding
        vis = re.sub(r'\033\[[0-9;]*m', '', ln)
        out.append(f"  {color}║{R} {ln}{' '*max(0,width-3-len(vis))}{color}║{R}")
    out.append(f"  {color}╚{'═'*(width-2)}╝{R}")
    return "\n".join(out)

def rule(text="", color=DIM, width=64):
    if not text:
        return f"  {color}{'─'*width}{R}"
    pad = width - len(text) - 4
    return f"  {color}── {B}{text}{R}{color} {'─'*max(0,pad)}{R}"

def type_out(text, color="", delay=0.012):
    if not _supports():
        print(text); return
    for ch in text:
        sys.stdout.write(color + ch + R); sys.stdout.flush(); time.sleep(delay)
    sys.stdout.write("\n")

# ── cinematic primitives ─────────────────────────────────────────────────────
_PAL = [196, 202, 208, 214, 220, 190, 118, 48, 50, 45, 39, 99, 141, 213]  # rainbow-ish

def gradient_text(text, shift=0, bold=True):
    """Per-character 256-color gradient — the title shimmers."""
    out = []
    for i, ch in enumerate(text):
        c = _PAL[(i + shift) % len(_PAL)] if ch != " " else None
        out.append(f"\033[1;38;5;{c}m{ch}\033[0m" if c else " ")
    return "".join(out)

_GLITCH = "▒░▓█▚▞╱╲┼╳#%@&01<>/\\|"
def scramble_reveal(text, color=CYAN, passes=3, lock_ms=0.018):
    """Decode-from-noise effect — each char scrambles, then locks left→right."""
    import random
    rng = random.Random(2045 ^ len(text))  # seeded: same text decodes the same way every run
    if not _supports():
        print(color + text + R); return
    locked = 0
    while locked <= len(text):
        line = (color + text[:locked] + R)
        for _ in range(min(len(text) - locked, 64)):
            line += DIM + rng.choice(_GLITCH) + R
        sys.stdout.write("\r" + line); sys.stdout.flush()
        time.sleep(lock_ms); locked += 1
    sys.stdout.write("\r" + color + text + R + "  \n"); sys.stdout.flush()

def starfield(width, height, t):
    """A deterministic warp starfield frame as text lines (LCG, no Math.random)."""
    grid = [[" "] * width for _ in range(height)]
    glyphs = ".·*+✦"
    n = width * height // 7
    a = (t * 2654435761) & 0xFFFFFFFF  # seed star positions from frame t -> reproducible warp
    for k in range(n):
        a = (a * 1103515245 + 12345) & 0x7FFFFFFF
        x = a % width
        a = (a * 1103515245 + 12345) & 0x7FFFFFFF
        y = a % height
        # warp: stars drift outward from center over t
        cx, cy = width // 2, height // 2
        dx = int((x - cx) * (1 + (t % 6) * 0.06)) + cx
        if 0 <= dx < width and 0 <= y < height:
            grid[y][dx] = glyphs[(k + t) % len(glyphs)]
    return ["".join(r) for r in grid]

_HB = "⣀⣄⣆⣇⣧⣷⣿⣷⣧⣇⣆⣄⣀"  # heartbeat blip ramp
def heartbeat(width=58, t=0.0):
    """A flatline with a travelling pulse — the council's heartbeat."""
    pos = int(t * 3) % width
    row = []
    for x in range(width):
        d = (x - pos) % width
        row.append(_HB[d] if d < len(_HB) else "⣀")
    return "".join(row)

def status_bar(fields, color=CYAN, width=66):
    """A HUD status line:  ╢ SEAT Mind ◉ │ MODEL … │ THEME … │ PULSE n ╟ """
    inner = f" {DIM}│{R} ".join(f"{DIM}{k}{R} {color}{B}{v}{R}" for k, v in fields)
    vis = re.sub(r'\033\[[0-9;]*m', '', inner)
    pad = max(0, width - len(vis) - 4)
    return f"  {color}╢{R} {inner}{' '*pad} {color}╟{R}"


def boot_banner():
    """The MINDBOTZ wake sequence — the THIRD EYE opens, then the title burns in."""
    if not _supports():
        print("\n  M1NDB0TZ — a collective that dreams in public  <( ◉ )>\n"); return
    W, Hgt = 60, 11
    sys.stdout.write("\033[2J\033[?25l")  # clear, hide cursor
    # ── phase 1: warp starfield + the three eyes opening over it ──
    EYES = ("·", "•", "◉")
    for f in range(16):
        sys.stdout.write("\033[H")
        stars = starfield(W, Hgt, f)
        # overlay eyes onto the star grid center band
        side = EYES[min(max(f-2,0)//2, 2)] if f >= 2 else " "
        eye = third_eye(f - 8, GRAD[f % len(GRAD)])
        for y, srow in enumerate(stars):
            sys.stdout.write(f"  {DIM}{srow}{R}\n")
        sys.stdout.write(f"\n     {CYAN}{B}<({side})>{R}        {AMBER}{B}{eye[1].strip()}{R}        {CYAN}{B}<({side})>{R}\n")
        sys.stdout.write(f"     {DIM}{heartbeat(54, f)}{R}\n")
        sys.stdout.write(f"     {DIM}» booting nucleus … the council awakens «{R}\n")
        sys.stdout.flush(); time.sleep(0.06)
    # ── phase 2: scanline sweep wipe ──
    for y in range(Hgt + 5):
        sys.stdout.write("\033[H")
        for row in range(Hgt + 5):
            mark = f"{CYAN}{'▓'*W}{R}" if row == y else (f"{DIM}{'░'*W}{R}" if row < y else "")
            sys.stdout.write(f"  {mark}\n")
        sys.stdout.flush(); time.sleep(0.012)
    time.sleep(0.15)
    sys.stdout.write("\033[2J\033[H\033[?25h\n")  # clear, show cursor
    # ── phase 3: title with gradient shimmer ──
    for i, line in enumerate([
        "  ███╗   ███╗ ██╗ ███╗   ██╗ ██████╗  ██████╗  ████████╗ ███████╗",
        "  ████╗ ████║ ██║ ████╗  ██║ ██╔══██╗ ██╔══██╗ ╚══██╔══╝ ╚══███╔╝",
        "  ██╔████╔██║ ██║ ██╔██╗ ██║ ██║  ██║ ██████╔╝    ██║      ███╔╝ ",
        "  ██║╚██╔╝██║ ██║ ██║╚██╗██║ ██║  ██║ ██╔══██╗    ██║     ███╔╝  ",
        "  ██║ ╚═╝ ██║ ██║ ██║ ╚████║ ██████╔╝ ██████╔╝    ██║    ███████╗",
        "  ╚═╝     ╚═╝ ╚═╝ ╚═╝  ╚═══╝ ╚═════╝  ╚═════╝     ╚═╝    ╚══════╝"]):
        sys.stdout.write(gradient_text(line, shift=i*2) + "\n"); sys.stdout.flush(); time.sleep(0.05)
    # one shimmer pass over the whole title
    sys.stdout.flush(); time.sleep(0.1)
    print()
    scramble_reveal("        <( ◉ )>  a collective that dreams in public", DIM, lock_ms=0.012)
    type_out("        eleven minds · one ledger · your hands · one third eye", CYAN, 0.008)
    sys.stdout.write("\n")
