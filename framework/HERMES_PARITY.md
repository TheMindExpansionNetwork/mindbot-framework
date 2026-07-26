# Hermes / OpenClaw / Claude Code feature parity — council edition

*The founder runs Hermes today. This framework must be a superset where it matters
and honestly mark what's deferred. Checked 2026-06-11.*

| capability | Hermes/OpenClaw/Claude Code | M1NDB0TZ council | status |
|---|---|---|---|
| SKILL.md skills | yes | 17_/skills, same frontmatter contract | ✅ compatible |
| skill marketplace use | yes | any SKILL.md loads unchanged | ✅ by format |
| cron / scheduled work | yes | state.json cron table + crontab.vps + windows_task.ps1 | ✅ |
| delegation / subagents | yes | 11 counselors + domain routing | ✅ (richer) |
| memory | profile memories | 12_ handoffs + ledger + SOUL.md (file-based, model-agnostic) | ✅ different shape, deliberate |
| tool calling | native | counselors use their host runtimes (Claude Code, Hermes, etc.); nucleus stays stdlib | ✅ hybrid by design |
| multi-model | partial | OpenRouter one-key + per-provider + local fallback | ✅ superset |
| dreaming / self-skill-creation | no | dream_cycle + skill_dreamer (status: dreamed → test → active) | ✅ novel |
| self-training loop | no | weekly Second Sleep (LoRA/GRPO on own handoffs) | ✅ novel |
| public ledger | no | ledger.jsonl, public-grade | ✅ novel |
| self-clone / git rollout | partial | deploy/git_backup.ps1 + fork-ready repo layout | ✅ |
| browser / web tools | yes | deferred to host runtimes; nucleus never transmits | ⏸ deliberate |
| voice / streaming | partial | night-shift-voice-pack + stream stages; OBS wiring | 🔜 launch week |
| cheat mode | no | Konami code on the dashboard (↑↑↓↓←→←→BA) | ✅ because joy matters |

**Interop rule:** current Hermes can drive this framework today — point it at the
workspace, have it run `python -m mindbot_pipeline.cli pulse` and read/write the 12_
files. The council doesn't replace your agents; it gives them seats.
