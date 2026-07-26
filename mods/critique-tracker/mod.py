import json
import time
from pathlib import Path

DB_PATH = Path("mods/critique-tracker/critiques.json")


def _load_db() -> list:
    if DB_PATH.exists():
        try:
            with DB_PATH.open("r") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save_db(data: list) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DB_PATH.open("w") as f:
        json.dump(data, f, indent=2)


def register(api):
    @api.command("critique record", "Record a critique score: critique record <counselor> <score 1-10> [task-id] [notes]")
    def critique_record(arg: str) -> None:
        parts = arg.strip().split(maxsplit=3)
        if len(parts) < 2:
            api.say("Usage: critique record <counselor> <score 1-10> [task-id] [notes]")
            return

        counselor = parts[0]
        try:
            score = int(parts[1])
        except ValueError:
            api.say("Score must be an integer 1-10")
            return

        if not 1 <= score <= 10:
            api.say("Score must be between 1 and 10")
            return

        task_id = parts[2] if len(parts) >= 3 else None
        notes = parts[3] if len(parts) >= 4 else ""

        entry = {
            "counselor": counselor,
            "score": score,
            "task_id": task_id,
            "notes": notes,
            "timestamp": time.time(),
        }

        db = _load_db()
        db.append(entry)
        _save_db(db)

        task_str = f" for task {task_id}" if task_id else ""
        api.say(f"Recorded critique: {counselor} scored {score}/10{task_str}")

    @api.command("critique stats", "Show counselor rankings by average score: critique stats [--top N]")
    def critique_stats(arg: str) -> None:
        db = _load_db()
        if not db:
            api.say("No critiques recorded yet.")
            return

        top_n = None
        args = arg.strip().split()
        if args and args[0] == "--top":
            if len(args) < 2:
                api.say("Usage: critique stats [--top N]")
                return
            try:
                top_n = int(args[1])
            except ValueError:
                api.say("Invalid number for --top")
                return

        stats = {}
        for entry in db:
            c = entry["counselor"]
            if c not in stats:
                stats[c] = {"total": 0, "count": 0}
            stats[c]["total"] += entry["score"]
            stats[c]["count"] += 1

        ranked = []
        for counselor, data in stats.items():
            avg = data["total"] / data["count"]
            ranked.append((counselor, avg, data["count"]))

        ranked.sort(key=lambda x: (-x[1], -x[2]))

        if top_n:
            ranked = ranked[:top_n]

        lines = ["Counselor Rankings by Average Score:", "-" * 48]
        for i, (counselor, avg, count) in enumerate(ranked, 1):
            lines.append(f"{i}. {counselor}: {avg:.2f} avg ({count} reviews)")

        api.say("\n".join(lines))

    @api.command("critique history", "Show all critiques for a counselor: critique history <counselor>")
    def critique_history(arg: str) -> None:
        counselor = arg.strip()
        if not counselor:
            api.say("Usage: critique history <counselor>")
            return

        db = _load_db()
        entries = [e for e in db if e["counselor"].lower() == counselor.lower()]

        if not entries:
            api.say(f"No critiques found for counselor: {counselor}")
            return

        lines = [f"Critique history for {counselor}:", "-" * 48]
        for e in entries:
            ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(e["timestamp"]))
            task = f" (task: {e['task_id']})" if e["task_id"] else ""
            notes = f" - {e['notes']}" if e["notes"] else ""
            lines.append(f"  {ts}: {e['score']}/10{task}{notes}")

        api.say("\n".join(lines))

    @api.command("critique import", "Scan ledger for historical critiques and populate local DB")
    def critique_import(arg: str) -> None:
        api.log("Scanning ledger for historical critiques...")
        entries = api.entries(event="critique", limit=0)

        if not entries:
            api.log("No 'critique' events found, trying generic scan...")
            all_entries = api.entries(limit=0)
            entries = [e for e in all_entries if isinstance(e, dict) and e.get("type") == "critique"]

        if not entries:
            api.say("No historical critiques found in ledger.")
            return

        db = _load_db()
        existing_keys = {(e["counselor"], e["score"], e.get("task_id"), e["timestamp"]) for e in db}
        imported = 0

        for entry in entries:
            try:
                if not isinstance(entry, dict):
                    continue

                counselor = entry.get("counselor") or entry.get("author")
                score = entry.get("score")
                task_id = entry.get("task_id") or entry.get("task")
                notes = entry.get("notes") or entry.get("message") or ""
                timestamp = entry.get("timestamp") or entry.get("time") or time.time()

                if counselor and score is not None and 1 <= int(score) <= 10:
                    key = (counselor, int(score), task_id, timestamp)
                    if key not in existing_keys:
                        db.append({
                            "counselor": counselor,
                            "score": int(score),
                            "task_id": task_id,
                            "notes": notes,
                            "timestamp": timestamp,
                        })
                        existing_keys.add(key)
                        imported += 1
            except Exception as e:
                api.log(f"Failed to parse ledger entry: {e}")
                continue

        _save_db(db)
        api.say(f"Imported {imported} historical critiques from ledger.")
