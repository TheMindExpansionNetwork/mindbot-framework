"""ledger-lens — make the hash-chained ledger legible.

The ledger is the most valuable artifact this framework produces and the least readable: a
thousand-plus lines of JSON. This mod does arithmetic over it and answers the three questions a
human actually has — when does it work, how consistently, and is the output getting better.

ZERO MODEL CALLS. It never declares `model`, so the static audit refuses to load it if this file
ever reaches for one. "Costs nothing" is enforced, not promised.
"""
from collections import Counter


def register(api):

    def _entries():
        return api.entries()                      # needs 'ledger.read'

    # ---------------------------------------------------------------- pulse

    @api.command("pulse", "activity by hour — when does the council actually work?")
    def pulse(arg):
        rows = _entries()
        if not rows:
            api.say("ledger is empty")
            return {}
        hours = Counter(e["ts"][11:13] for e in rows if len(e.get("ts", "")) >= 13)
        peak = max(hours.values())
        api.say(f"\n  {len(rows)} recorded actions across {len(hours)} active hours\n")
        for h in sorted(hours):
            # Bar width scaled to the busiest hour, so the shape reads at any volume.
            bar = "█" * max(1, round(hours[h] / peak * 34))
            api.say(f"   {h}:00  {bar} {hours[h]}")
        busiest = max(hours, key=hours.get)
        api.say(f"\n   busiest hour: {busiest}:00 ({hours[busiest]} actions)")
        api.log(f"pulse: {len(rows)} entries, peak {busiest}:00")
        return dict(hours)

    # --------------------------------------------------------------- streak

    @api.command("streak", "consecutive active days, longest run, and the quiet gaps")
    def streak(arg):
        rows = _entries()
        days = sorted({e["ts"][:10] for e in rows if len(e.get("ts", "")) >= 10})
        if not days:
            api.say("no dated entries")
            return {}
        from datetime import date

        def d(s):
            y, m, dd = (int(x) for x in s.split("-"))
            return date(y, m, dd)

        best = run = 1
        gaps = []
        for i in range(1, len(days)):
            delta = (d(days[i]) - d(days[i - 1])).days
            if delta == 1:
                run += 1
                best = max(best, run)
            else:
                if delta > 1:
                    gaps.append((days[i - 1], days[i], delta - 1))
                run = 1
        api.say(f"\n  active on {len(days)} days · {days[0]} → {days[-1]}")
        api.say(f"   longest streak: {best} day(s)")
        api.say(f"   current streak: {run} day(s)")
        if gaps:
            api.say(f"\n   quiet gaps:")
            for a, b, n in gaps[-5:]:
                api.say(f"     {n} day(s) between {a} and {b}")
        api.log(f"streak: {len(days)} active days, longest {best}")
        return {"active_days": len(days), "longest": best, "current": run}

    # -------------------------------------------------------------- quality

    @api.command("quality", "studio critique scores over time — is the output improving?")
    def quality(arg):
        """The interesting one.

        The studio ledgers every critique round with its score, so the framework carries a
        tamper-evident series of its OWN output quality. Not a changelog anyone can edit after
        the fact — an append-only, externally anchored record.
        """
        rows = api.entries("studio_critique")
        if not rows:
            api.say("no studio critiques recorded yet — run: mindbot studio \"<task>\"")
            return {}
        by_day = {}
        for e in rows:
            day = e["ts"][:10]
            # detail looks like: "round 1 score=6/10 verdict=revise fixes=3"
            try:
                score = int(e["detail"].split("score=")[1].split("/")[0])
            except (IndexError, ValueError):
                continue
            by_day.setdefault(day, []).append(score)
        if not by_day:
            api.say("critique entries found but none carried a parseable score")
            return {}
        api.say(f"\n  {len(rows)} critique round(s) across {len(by_day)} day(s)\n")
        for day in sorted(by_day):
            s = by_day[day]
            avg = sum(s) / len(s)
            bar = "▓" * round(avg) + "░" * (10 - round(avg))
            api.say(f"   {day}  {bar} {avg:.1f}/10   ({len(s)} rounds)")
        firsts = by_day[sorted(by_day)[0]]
        lasts = by_day[sorted(by_day)[-1]]
        drift = sum(lasts) / len(lasts) - sum(firsts) / len(firsts)
        verdict = ("improving" if drift > 0.5 else
                   "declining" if drift < -0.5 else "flat")
        api.say(f"\n   trend: {verdict} ({drift:+.1f} points)")
        if verdict == "flat":
            # Honest advice rather than flattery — a flat line means the extra calls aren't
            # buying anything, and the operator is paying for them.
            api.say("   flat means the critique loop isn't earning its extra calls.")
            api.say("   try: sharper per-kind criteria, or a critic on a stronger model.")
        api.log(f"quality: {len(rows)} rounds, trend {verdict} ({drift:+.1f})")
        return {"rounds": len(rows), "trend": verdict, "drift": round(drift, 2)}

    # --------------------------------------------------------------- report

    @api.command("report", "write all of the above to the outbox")
    def report(arg):
        rows = _entries()
        events = Counter(e.get("event", "?") for e in rows)
        days = sorted({e["ts"][:10] for e in rows if len(e.get("ts", "")) >= 10})
        crit = api.entries("studio_critique")
        lines = [
            f"# Ledger report",
            "",
            f"- **{len(rows)}** recorded actions",
            f"- **{len(days)}** active days ({days[0]} → {days[-1]})" if days else "",
            f"- **{len(crit)}** studio critique rounds",
            "",
            "## What it spends its time on",
            "",
            "| event | count |",
            "|---|--:|",
        ]
        lines += [f"| `{e}` | {n} |" for e, n in events.most_common(15)]
        lines += [
            "",
            "---",
            "",
            "Every number here was counted from the hash-chained ledger, not asserted.",
            "Verify the chain behind it: `mindbot verify` · `mindbot notarize --audit`",
        ]
        path = api.draft("ledger report", "\n".join(l for l in lines if l is not None))
        api.log(f"report: {len(rows)} entries summarized")
        api.say(f"report written — {len(rows)} actions, {len(events)} event types")
        return path
