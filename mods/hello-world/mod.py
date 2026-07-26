"""hello-world — the reference MindBot mod.

Read this file to learn the whole contract. Three things are true of every mod, including this
one, and none of them are optional:

  * It receives a `api` object that only HAS the capabilities its MOD.md declared.
  * Every action it takes writes a hash-chained ledger entry that the notary anchors.
  * Reaching for an undeclared capability raises CapabilityDenied — and records the attempt.

That is why you can run a mod you did not write and still prove what it did.
"""


def register(api):
    """Called once when the mod loads. Declare commands with @api.command."""

    @api.command("hello", "say hello and leave a receipt in the outbox")
    def hello(arg):
        who = (arg or "world").strip()
        # api.log is ALWAYS available — a mod cannot opt out of being recorded.
        api.log(f"greeted {who}")
        # api.draft needs 'outbox.write', which this mod declared. Drafts never send.
        path = api.draft(
            f"hello {who}",
            f"Hello, {who}.\n\n"
            "This draft was written by a third-party mod. You did not have to trust it — "
            "every action it took is in the hash-chained ledger and covered by the notary's "
            "Merkle root. Run `mindbot verify` and `mindbot notarize --audit` to confirm.\n",
        )
        api.say(f"hello, {who} — draft written")
        api.say(f"receipt: this greeting is now in the ledger (mod_log + mod_draft)")
        return path

    @api.command("peek", "read the board — a granted, audited capability")
    def peek(arg):
        tasks = api.board()                      # needs 'board.read'
        open_n = sum(1 for t in tasks if not t["done"])
        api.log(f"peeked at the board ({open_n} open)")
        api.say(f"the board has {open_n} open tasks (of {len(tasks)})")
        return {"open": open_n, "total": len(tasks)}

    @api.command("overreach", "DEMO: deliberately reach for a capability we did not declare")
    def overreach(arg):
        api.say("attempting api.ask(...) — this mod never declared 'model'…")
        # This raises CapabilityDenied AND writes a `mod_denied` ledger entry. The runtime
        # catches it and reports it; the attempt is permanently on the record.
        return api.ask("This call should never reach a model.")
