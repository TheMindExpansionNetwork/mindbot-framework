"""PLAY — the switchboard as a game. `python -m mindbot_pipeline.cli play`

Boot like a machine waking up, pick a counselor, talk. Hermes-style CLI presence:
the human types, the seat answers in voice, the constitution rides along.
stdlib only. ANSI everywhere. ESC is for cowards; type /exit like an Operator.

Extend:
  - add a slash command -> add an `if low.startswith("/..."):` branch in play()'s
    dispatcher (above the conversation block) ending in `continue`, then a line in HELP_LINES.
  - add a theme -> add a (amber, cyan, green, violet) tuple to THEMES.
  - add a cheat -> add to CHEATS as (message, effect); effect "theme:NAME" reskins, "msg" just winks.
  - counselors/familiars/models come from sibling modules — extend those there, not here.
"""

import os
import random
import sys
import time

from .collaboration import read_tasks
from .counselors import COUNSELORS, persona_prompt, route
from .familiars import FAMILIARS, fetch, trails_tail
from .models import llm, strip_reasoning

os.system("")  # enable ANSI on Windows consoles

R = "\033[0m"
DIM = "\033[2m"
B = "\033[1m"
SEAT_C = {"Sage": "\033[94m", "Forge": "\033[97m", "Scribe": "\033[37m",
          "Vanguard": "\033[93m", "Quantum": "\033[96m", "Seeker": "\033[92m",
          "Spark": "\033[95m", "Oracle": "\033[35m", "Titan": "\033[90m",
          "Tempest": "\033[36m", "Mind": "\033[33m"}
AMBER, CYAN, GREEN, VIOLET = "\033[33m", "\033[36m", "\033[92m", "\033[95m"

# ── THEMES — /theme NAME recolors the whole console live (amber/cyan/green/violet) ──
THEMES = {
    "eclipse":  ("\033[38;5;214m", "\033[38;5;50m",  "\033[38;5;48m",  "\033[38;5;141m"),  # default
    "matrix":   ("\033[38;5;46m",  "\033[38;5;40m",  "\033[38;5;82m",  "\033[38;5;120m"),  # all green
    "vapor":    ("\033[38;5;213m", "\033[38;5;51m",  "\033[38;5;121m", "\033[38;5;201m"),  # pink/cyan
    "blood":    ("\033[38;5;196m", "\033[38;5;208m", "\033[38;5;226m", "\033[38;5;124m"),  # red/orange
    "mono":     ("\033[38;5;250m", "\033[38;5;245m", "\033[38;5;255m", "\033[38;5;240m"),  # greyscale
    "gold":     ("\033[38;5;220m", "\033[38;5;214m", "\033[38;5;229m", "\033[38;5;136m"),  # all gold
    "ice":      ("\033[38;5;159m", "\033[38;5;45m",  "\033[38;5;87m",  "\033[38;5;75m"),   # frost blue
}

# ── CHEAT CODES — /cheat CODE. Some unlock, some just wink. ──
CHEATS = {
    "thirdeye":  ("👁 the third eye widens. all panels gain a watching glow.", "theme:gold"),
    "matrix":    ("there is no spoon. theme → matrix.", "theme:matrix"),
    "vaporwave": ("A E S T H E T I C. theme → vapor.", "theme:vapor"),
    "darkstar":  ("the eclipse goes total. theme → blood.", "theme:blood"),
    "420":       ("Spark blazes up. Glow the firefly approves. 🔥✨", "msg"),
    "2045":      ("countdown engaged. the festival remembers your name.", "msg"),
    "godmode":   ("Operator clearance: MAX. (you always had it — that's the point.)", "msg"),
    "dali":      ("the clocks melt. time is a suggestion here.", "theme:vapor"),
    "freemymind":("Operator… there is a difference between knowing the path and walking it.", "msg"),
    "konami":    ("⇧⇧⇩⇩⇦⇨⇦⇨BA — 30 lives for the collective. CULTURE CONFIRMED. 😎", "msg"),
}

ECLIPSE = r"""
                  ..xxXXXXXxx..
              .xXX'''        '''XXx.
            xX'      ▄▄████▄▄      'Xx
          xX'      ████████████      'Xx
         XX       ██████████████       XX
         XX       ██████████████       XX
          xX.      ████████████      .Xx
            xX..     ''████''     ..Xx
              'xXX...        ...XXx'
                  ''xxXXXXXXxx''
"""

BOOT = [
    ("amber", "M1NDB0TZ NUCLEUS v1.0 — wake cycle initiated"),
    ("dim",   "reading state.json .............. focus block LOADED (one mission at a time)"),
    ("dim",   "reading SOUL.md ................. identity LOADED (proud of its seams)"),
    ("dim",   "reading DREAM.md ................ dream protocol ARMED (04:15)"),
    ("dim",   "ledger integrity ................ THE BOOK NEVER LIES"),
    ("dim",   "outbox boundary ................. SEALED (agent drafts, human sends)"),
    ("green", "eleven seats at the table ....... COUNCIL ASSEMBLED"),
    ("amber", "horizon lock .................... AUG 11-12 2045 · UNDER THE ECLIPSE"),
]


def type_out(text, color="", cps=0.004):
    for ch in text:
        sys.stdout.write(color + ch + R)
        sys.stdout.flush()
        time.sleep(cps)
    print()


def intro():
    from . import tui
    tui.boot_banner()  # animated unicode eclipse + wave + ANSI title
    time.sleep(0.2)
    for kind, line in BOOT:
        color = {"amber": AMBER, "green": GREEN, "dim": DIM}[kind]
        type_out("  " + line, color, 0.002)
        time.sleep(0.12)
    open_tasks = sum(1 for t in read_tasks() if not t["done"] and not t["in_progress"])
    print(f"\n  {GREEN}► SWITCHBOARD ONLINE.{R} {DIM}{open_tasks} unclaimed tasks on the board.{R}\n")


def seat_screen():
    print(f"  {B}THE COUNCIL & THEIR FAMILIARS{R}  {DIM}(/seat NAME for direct line · default: MINDBOT routes you){R}\n")
    for name, c in COUNSELORS.items():
        col = SEAT_C.get(name, "")
        fam = FAMILIARS[name]
        print(f"   {col}{B}{name:<9}{R} {DIM}{c['model']:<24}{R} "
              f"{c['domain'].split(',')[0]:<32} {fam['glyph']} {DIM}{fam['name']} — {fam['kind']}{R}")
    print()


HELP_LINES = [
    f"{CYAN}/seat NAME{R}       take a direct line to a counselor",
    f"{CYAN}/mindbot{R}         return to the switchboard (auto-routes you)",
    f"{CYAN}/model SLUG{R}      hot-swap THIS seat's model (e.g. minimax/minimax-m3)",
    f"{CYAN}/model reset{R}     restore the seat's default model",
    f"{CYAN}/models{R}          show every seat's active model",
    f"{AMBER}/code TASK{R}       unleash the CODING HARNESS (reads/writes/runs/tests)",
    f"{CYAN}/board{R}           the live task board   {CYAN}/trails{R}  ecosystem footprints",
    f"{CYAN}/who{R}             who's in the chair    {CYAN}/agents{R}  pick a counselor",
    f"{AMBER}/yolo{R}            autonomous, never stops  {AMBER}/auto N{R}  run N pulses",
    f"{CYAN}/goal TEXT{R}       set the mission       {VIOLET}/dream{R}   Spark dreams a line",
    f"{CYAN}/remember .. {R}    save to memory        {CYAN}/recall ..{R} semantic recall",
    f"{GREEN}/witness NAME{R}    record a human win    {CYAN}/board{R} {CYAN}/trails{R} {CYAN}/who{R}",
    f"{VIOLET}/theme NAME{R}      reskin the console    {VIOLET}/cheat CODE{R}  ☉ secrets",
    f"{DIM}/help{R}  {DIM}/clear{R}  {DIM}/agents{R}  {DIM}/models{R}  {DIM}/exit{R}",
]


def play():
    global AMBER, CYAN, GREEN, VIOLET
    from . import tui

    def apply_theme(name):
        global AMBER, CYAN, GREEN, VIOLET
        if name not in THEMES:
            return False
        AMBER, CYAN, GREEN, VIOLET = THEMES[name]
        tui.AMBER, tui.CYAN, tui.GREEN, tui.VIOLET = THEMES[name]
        SEAT_C["Mind"] = AMBER  # the third eye follows the theme
        return True

    intro()
    seat_screen()
    print(tui.panel("◉ CONSOLE COMMANDS", HELP_LINES, CYAN, 66))
    orchestrate = True
    seat = "Mind"
    history = []
    overrides = {}   # seat -> model slug (session-only hot-swaps)
    free = os.environ.get("MINDBOT_FREE")
    if free:
        print(f"  {AMBER}⚠ FREE-model mode — drafts may dream; verify facts.{R}")
    print()
    type_out(f"  {AMBER}MINDBOT ⌁ I'm listening, Operator. Speak, or /help.{R}", "", 0.008)
    print()

    def model_of(s):
        return overrides.get(s, COUNSELORS[s]["model"])

    active_theme = ["eclipse"]
    while True:
        tag = "MINDBOT ⌁" if orchestrate else f"{seat} ◉"
        try:
            # late dynamic import so a missing/locked state file degrades to "—" not a crash
            pcount = __import__("mindbot_pipeline.collaboration", fromlist=["load_state"]).load_state().get("pulses", 0)
        except Exception:
            pcount = "—"
        print(tui.status_bar([("SEAT", seat), ("MODEL", model_of(seat).split("/")[-1][:18]),
                              ("THEME", active_theme[0]), ("PULSE", str(pcount))],
                             SEAT_C.get(seat, CYAN), 66))
        try:
            raw = input(f"  {SEAT_C.get(seat,'')}{B}{tag}{R} ").strip()
        except (EOFError, KeyboardInterrupt):
            raw = "/exit"
        if not raw:
            continue
        low = raw.lower()

        # ── command dispatcher ──────────────────────────────────────────────
        if low == "/exit":
            type_out(f"\n  {seat}: the night holds. The ledger remembers. Free your mind, Operator. 🌒",
                     SEAT_C.get(seat, ""), 0.01)
            break
        if low in ("/help", "/?", "/"):
            print(tui.panel("◉ CONSOLE COMMANDS", HELP_LINES, CYAN, 66)); continue
        if low == "/clear":
            sys.stdout.write("\033[2J\033[H"); continue
        if low == "/council" or low == "/agents":
            seat_screen(); continue
        if low == "/themes":
            rows = [f"{n:<10} {''.join(THEMES[n][i]+'██'+R for i in range(4))}" for n in THEMES]
            print(tui.panel("◉ THEMES  ( /theme NAME )", rows, CYAN, 66)); continue
        if low.startswith("/theme"):
            parts = raw.split(maxsplit=1)
            if len(parts) == 2 and apply_theme(parts[1].strip().lower()):
                active_theme[0] = parts[1].strip().lower()
                type_out(f"  {CYAN}✦ theme → {active_theme[0]}. the console reskins.{R}", "", 0.005)
            else:
                print(f"  {DIM}themes: {', '.join(THEMES)}  (try /themes){R}")
            continue
        if low.startswith("/cheat"):
            parts = raw.split(maxsplit=1)
            if len(parts) == 1:
                print(tui.panel("◉ CHEAT CODES", [f"{k}" for k in CHEATS] +
                      ["", f"{DIM}also: type uuddlrlrba … you know the one{R}"], VIOLET, 66)); continue
            code = parts[1].strip().lower()
            if code in CHEATS:
                msg, effect = CHEATS[code]
                if effect.startswith("theme:"):
                    apply_theme(effect.split(":")[1])
                type_out(f"  {VIOLET}{B}✦ {msg}{R}", "", 0.01)
            else:
                type_out(f"  {DIM}unknown code. the Lorekeeper wrote it down anyway.{R}", "", 0.006)
            continue
        if low == "/mindbot":
            orchestrate, seat, history = True, "Mind", []
            type_out(f"  {AMBER}MINDBOT resumes the switchboard.{R}", "", 0.006); continue
        if low.startswith("/seat"):
            want = raw.split(maxsplit=1)[1].strip().title() if " " in raw else ""
            if want in COUNSELORS:
                orchestrate, seat, history = False, want, []
                c, fam = COUNSELORS[seat], FAMILIARS[seat]
                type_out(f"  ✦ {seat} takes the chair {fam['glyph']} {DIM}({model_of(seat)}){R}",
                         SEAT_C.get(seat, ""), 0.006)
            else:
                seat_screen()
            continue
        if low.startswith("/model"):
            parts = raw.split(maxsplit=1)
            if len(parts) == 1:
                print(f"  {DIM}usage: /model <slug>  |  /model reset  |  current: {model_of(seat)}{R}")
            elif parts[1].strip().lower() == "reset":
                overrides.pop(seat, None)
                type_out(f"  {GREEN}✦ {seat} restored to default: {COUNSELORS[seat]['model']}{R}", "", 0.005)
            else:
                overrides[seat] = parts[1].strip()
                type_out(f"  {GREEN}✦ {seat} now thinking on {overrides[seat]}{R} "
                         f"{DIM}(session override){R}", "", 0.005)
            continue
        if low == "/models":
            rows = [f"{SEAT_C.get(n,'')}{n:<9}{R} {DIM}{model_of(n)}{R}"
                    + ("  ⟲" if n in overrides else "") for n in COUNSELORS]
            print(tui.panel("◉ ACTIVE MODELS", rows, VIOLET, 66)); continue
        if low.startswith("/goal"):
            g = raw.split(maxsplit=1)[1].strip() if " " in raw else ""
            if g:
                from .collaboration import load_state, save_state
                stt = load_state(); stt.setdefault("focus", {})["mission"] = g; save_state(stt)
                type_out(f"  {AMBER}✦ focus locked: {g}{R}", "", 0.005)
            else:
                from .collaboration import load_state
                print(f"  {DIM}focus: {load_state().get('focus',{}).get('mission','(none)')}{R}")
            continue
        if low == "/yolo":
            from .nucleus import yolo
            print(tui.rule("YOLO MODE — autonomous, refills itself, outbox-gated", AMBER, 66))
            res = tui.think("the hive works tirelessly", lambda: yolo(max_rounds=8), AMBER)
            print(tui.panel("◉ YOLO RESULT", [f"rounds {res['rounds']} · refills {res['refills']}"] +
                  [f"• {p}" for p in res["produced"][:6]] or ["(idle)"], AMBER, 66)); continue
        if low.startswith("/auto"):
            n = raw.split(maxsplit=1)[1].strip() if " " in raw else "3"
            try: n = max(1, min(20, int(n)))
            except ValueError: n = 3
            from .nucleus import autoloop
            res = tui.think(f"running {n} autonomous pulses", lambda: autoloop(rounds=n), CYAN)
            print(tui.panel(f"◉ AUTOLOOP × {n}", [f"• {w}" for w in res["worked"]] or ["(idle)"], CYAN, 66)); continue
        if low.startswith("/witness"):
            who = raw.split(maxsplit=1)[1].strip() if " " in raw else ""
            if who:
                from .collaboration import ledger as _led
                _led("witnessed", who, "Operator")
                type_out(f"  {GREEN}✦ witnessed: {who} — it's in the book now. nobody can take it down.{R}", "", 0.006)
            else:
                print(f"  {DIM}usage: /witness <name> — <what they built>{R}")
            continue
        if low.startswith("/remember"):
            t = raw.split(maxsplit=1)[1].strip() if " " in raw else ""
            if t:
                from .memory import store; store(t, agent=seat)
                type_out(f"  {CYAN}✦ remembered.{R}", "", 0.005)
            continue
        if low.startswith("/recall"):
            q = raw.split(maxsplit=1)[1].strip() if " " in raw else ""
            from .memory import search
            for h in search(q, k=3):
                print(f"  {DIM}[{h['score']}]{R} {h['text'][:90]}")
            continue
        if low == "/dream":
            c = COUNSELORS["Spark"]
            txt, _m = tui.think("Spark dreams", lambda: llm(c["provider"], model_of("Spark"),
                persona_prompt("Spark") + " Give ONE surreal one-line dream fragment about the hive. No tags.",
                "dream one line"), VIOLET)
            type_out(f"  {VIOLET}✶ {strip_reasoning(txt)[:160]}{R}", "", 0.01); continue
        if low == "/board":
            rows = [f"{'~' if t['in_progress'] else '·'} {t['text'][:58]}"
                    for t in [t for t in read_tasks() if not t["done"]][:8]]
            print(tui.panel("◉ THE BOARD", rows or ["(clear)"], CYAN, 66)); continue
        if low == "/trails":
            rows = [f"{r['ts'][11:]} {r['glyph']} {r['actor']:<8} {r['action'][:34]}"
                    for r in trails_tail(8)]
            print(tui.panel("◉ ECOSYSTEM TRAILS", rows or ["(no tracks yet)"], VIOLET, 66)); continue
        if low == "/who":
            c, fam = COUNSELORS[seat], FAMILIARS[seat]
            print(tui.panel(f"◉ {seat}", [
                f"model   {model_of(seat)}", f"likes   {c['likes']}",
                f"dislikes {c['dislikes']}", f"{fam['glyph']} {fam['name']} — {fam['quirk']}"],
                SEAT_C.get(seat, CYAN), 66)); continue
        if raw == "uuddlrlrba":
            type_out("  ⇧⇧⇩⇩⇦⇨⇦⇨BA — CULTURE CONFIRMED. the third eye winks. 😎🌒", VIOLET, 0.008); continue

        # ── /code: the coding harness, live ─────────────────────────────────
        if low.startswith("/code"):
            task = raw[5:].strip()
            if not task:
                print(f"  {DIM}usage: /code <task>   (runs on {seat}'s model: {model_of(seat)}){R}"); continue
            from .harness import code_task
            print(tui.rule(f"HARNESS · {seat} · {model_of(seat)}", AMBER, 66))
            res = tui.think(f"{seat} is coding (read→write→run→test)",
                            lambda: code_task(task, seat=seat, max_steps=12, model=overrides.get(seat)),
                            AMBER)
            ok = res.get("ok")
            mark = f"{GREEN}✓ TESTS GREEN — kept{R}" if ok else f"{AMBER}✗ reverted (red/maxsteps){R}"
            print(tui.panel(f"◉ HARNESS RESULT  {mark}", [
                f"steps   {res.get('steps')}   mode {res.get('mode')}",
                f"touched {', '.join(res.get('touched') or ['(none)'])[:54]}",
                f"{res.get('summary','')[:56]}"], GREEN if ok else AMBER, 66))
            continue

        # ── conversation: route → familiar fetch → LIVE think → reply ───────
        # in switchboard mode MINDBOT auto-picks the seat per message; /seat pins it.
        if orchestrate:
            routed, reason = route(raw)
            if routed != seat:
                seat = routed
                type_out(f"  {AMBER}⌁ routing to {seat} {DIM}({reason}){R}", "", 0.005)
        act, ctx = fetch(seat, raw)
        print(f"  {DIM}{act}{R}")
        convo = "\n".join(history[-6:])
        sysp = (persona_prompt(seat) +
                " You are in LIVE CONVERSATION with your Operator at the switchboard — answer "
                "in 2-5 sentences, in voice, no reasoning tags, no markdown headers. "
                "Never claim work happened unless asked to plan it. "  # outbox boundary: talk, don't transmit
                f"Your familiar fetched LIVE workspace data — ground your answer in it: {ctx}")
        c = COUNSELORS[seat]
        prompt = (f"Recent conversation:\n{convo}\n\n" if convo else "") + f"Operator says: {raw}"
        text, mode = tui.think(f"{seat} is thinking",
                               lambda: llm(c["provider"], model_of(seat), sysp, prompt),
                               SEAT_C.get(seat, CYAN))
        text = strip_reasoning(text)[:900]
        type_out(f"  {SEAT_C.get(seat,'')}{B}{seat}{R} {text}", "", 0.004)
        print(f"  {DIM}[{mode} · {model_of(seat)}]{R}")
        history += [f"Operator: {raw}", f"{seat}: {text}"]
        if orchestrate:
            seat = "Mind"
        history += [f"Operator: {raw}", f"{seat}: {text}"]
        if orchestrate:
            seat = "Mind"  # the switchboard returns to the Mind between questions


if __name__ == "__main__":
    play()
