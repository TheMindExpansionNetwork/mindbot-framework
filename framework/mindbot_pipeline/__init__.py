"""MindBot Synergetic Cognition — pipeline framework.

The loop is the magic: wake → read state → do ONE task → verify → outbox → ledger → die.
Inherits the ARCHITECT nucleus pattern (14_/MINDBOT_HQ), extends it with the
11-counselor stack, the synthetic-data pipeline, and the reality-live launch path.

Constitution (binding, from MISSION.md):
  1. Agent drafts, human sends.
  2. Never fabricate — [NEED: ...] markers, not guesses.
  3. One mission at a time; the focus block is law.
  4. The ledger is public-grade.
  5. Autonomy is a direction, not a switch.
  6. Dignity over content.
  7. Ship small, prove, then replicate.

Horizon: the Intergalactic Music Festival, August 11-12, 2045 — the founder's
birthday, under the eclipse. Every design decision must survive until then:
plain files, plain JSON, no service that can't be replaced in an afternoon.

Where things live (for an agent adapting this — each module's docstring has an "Extend:" line):
  nucleus.py       the pulse + swarm + yolo + autopilot + evolve + reflect (autonomy loop)
  counselors.py    the 11 seats (lenses) + routing            models.py     the model router (any brain)
  collaboration.py board / ledger (hash-chained) / handoffs    harness.py    the coding harness (tests-judge)
  commerce.py      earn/spend/operate (Stripe)                 provenance.py verify() + attest() (proof)
  server.py        HTTP + /api/*                                mcp_server.py expose the hive over MCP
  cli.py           every `mindbot <cmd>`                        logs.py       operational logging
Each `mindbot` command = a subparser + an elif in cli.py:main(); keep the constitution clauses above.
"""

__version__ = "0.3.0"
HORIZON = "2045-08-12"
