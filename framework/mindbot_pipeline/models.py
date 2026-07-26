"""Model router — each counselor reaches its big model; everything degrades gracefully.

Priority per provider: env-key cloud API → local Ollama/LM Studio → template mode.
Template mode means the pulse NEVER stalls: with no model reachable, sessions still do
real local work (mining handoffs, bookkeeping, dashboard state) and queue the
generative work for a counselor that has a brain attached.

stdlib-only (urllib), so the VPS needs nothing but Python 3.10+.

Extend: add a cloud provider -> add to ENDPOINTS + a branch in validate_key() and in
llm() (reuse _openai_style for OpenAI-shaped APIs, else write a _provider() helper like
_anthropic); map a counselor model to OpenRouter -> add to OPENROUTER_SLUGS; route a model
to S0N1C -> add its id to SONIC_MODELS. Keep the fallback ORDER in llm() intact (see there).
"""

import json
import os
import urllib.request
from pathlib import Path

# .env loader — easy config, zero dependencies. framework/.env, KEY=VALUE lines.
_ENV = Path(__file__).resolve().parents[1] / ".env"
if _ENV.exists():
    for _line in _ENV.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ[_k.strip()] = _v.strip()

ENDPOINTS = {
    "anthropic": ("https://api.anthropic.com/v1/messages", "ANTHROPIC_API_KEY"),
    "openai":    ("https://api.openai.com/v1/chat/completions", "OPENAI_API_KEY"),
    "xai":       ("https://api.x.ai/v1/chat/completions", "XAI_API_KEY"),
    "deepseek":  ("https://api.deepseek.com/v1/chat/completions", "DEEPSEEK_API_KEY"),
    "google":    ("https://generativelanguage.googleapis.com/v1beta/models", "GOOGLE_API_KEY"),
    "mistral":   ("https://api.mistral.ai/v1/chat/completions", "MISTRAL_API_KEY"),
}

# OpenRouter: ONE key reaches every counselor's model. Checked FIRST when set —
# this is how the council runs on a $20 budget before the per-provider keys exist.
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# counselor model id → a REAL, role-matched OpenRouter slug (every slug live-validated
# 2026-06-22). This is what makes the premium per-seat council actually work with just a key:
# each lens gets a brain suited to its job, instead of one model wearing 11 hats. Slugs drift —
# re-check at openrouter.ai/models and update here when a model is retired.
OPENROUTER_SLUGS = {
    "claude-fable-5":        "anthropic/claude-opus-4.8",                 # Sage    — deep reasoning, orchestration
    "gpt-5":                 "moonshotai/kimi-k2.7-code",                 # Forge   — precision coding
    "claude-code":           "anthropic/claude-sonnet-4.6",              # Scribe  — docs + clear writing
    "grok-build":            "x-ai/grok-4.3",                            # Vanguard— bold, fast momentum
    "qwen3.6":               "qwen/qwen3.7-max",                         # Quantum — math + logic
    "deepseek-v4":           "deepseek/deepseek-v4-pro",                 # Seeker  — deep research
    "diffusion-gemma":       "google/gemini-3.5-flash",                  # Spark   — fast creative iteration
    "gemini-3-pro":          "google/gemini-3.1-pro-preview",            # Oracle  — multimodal planning
    "llama-4":               "meta-llama/llama-4-maverick",              # Titan   — robust at scale
    "mistral-large-3":       "mistralai/mistral-small-3.2-24b-instruct", # Tempest — rapid ideation
    "mindbot-synergetic-v1": "z-ai/glm-5.2",                             # Mind    — synthesis (validated brain)
}
OLLAMA = os.environ.get("OLLAMA_HOST", "http://localhost:11434")


def validate_key(provider: str, key: str) -> tuple[bool, str]:
    """Live-ping a provider key. Returns (ok, message). stdlib only.

    Real validation, not just 'is it set' — the disease this whole project keeps
    catching is stale keys that silently degrade the council to template mode.
    """
    import urllib.error
    try:
        if provider == "openrouter":
            req = urllib.request.Request("https://openrouter.ai/api/v1/key",
                                         headers={"Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(req, timeout=15) as r:
                return (r.status == 200, "live")
        if provider == "anthropic":
            req = urllib.request.Request(ENDPOINTS["anthropic"][0],
                data=json.dumps({"model": "claude-haiku-4-5-20251001", "max_tokens": 1,
                                 "messages": [{"role": "user", "content": "hi"}]}).encode(),
                headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return (r.status == 200, "live")
        if provider in ("openai", "xai", "deepseek", "mistral"):
            url = "https://api.openai.com/v1/models" if provider == "openai" else ENDPOINTS[provider][0]
            if provider != "openai":  # others: tiny chat ping
                req = urllib.request.Request(ENDPOINTS[provider][0],
                    data=json.dumps({"model": {"xai": "grok-2", "deepseek": "deepseek-chat",
                                     "mistral": "mistral-small-latest"}[provider],
                                     "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]}).encode(),
                    headers={"Authorization": f"Bearer {key}", "content-type": "application/json"})
            else:
                req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return (r.status == 200, "live")
        if provider == "google":
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={key}")
            with urllib.request.urlopen(req, timeout=15) as r:
                return (r.status == 200, "live")
    except urllib.error.HTTPError as e:
        return (False, f"HTTP {e.code} (key rejected)" if e.code in (401, 403) else f"HTTP {e.code}")
    except Exception as e:  # noqa: BLE001
        return (False, f"{type(e).__name__}")
    return (False, "unknown provider")


def write_env_key(name: str, value: str):
    """Upsert a KEY=VALUE into framework/.env (creating it if needed)."""
    lines = _ENV.read_text(encoding="utf-8").splitlines() if _ENV.exists() else []
    out, found = [], False
    for ln in lines:
        if ln.strip().startswith(f"{name}="):
            out.append(f"{name}={value}"); found = True
        else:
            out.append(ln)
    if not found:
        out.append(f"{name}={value}")
    _ENV.write_text("\n".join(out) + "\n", encoding="utf-8")
    os.environ[name] = value


def strip_reasoning(text: str) -> str:
    """Strip model thinking blocks: </think> and <start_working_out>…<end_working_out>.

    Our counselors are TRAINED to emit working-out tags — great for the dataset,
    noise in a live reply. This pulls just the answer/solution out.
    """
    import re as _re
    t = text.split("</think>")[-1]
    # prefer an explicit SOLUTION if present (our trained format)
    m = _re.search(r"<SOLUTION>(.*?)</SOLUTION>", t, flags=_re.S | _re.I)
    if m:
        return m.group(1).strip()
    # remove closed working-out blocks
    t = _re.sub(r"<start_working_out>.*?<end_working_out>", "", t, flags=_re.S | _re.I)
    # remove an UNCLOSED working-out block (truncated reasoning) to end-of-string
    t = _re.sub(r"<start_working_out>.*$", "", t, flags=_re.S | _re.I)
    # strip any stray tags + leftover marker lines
    t = _re.sub(r"</?(start_working_out|end_working_out|SOLUTION)>", "", t, flags=_re.I)
    t = "\n".join(l for l in t.splitlines() if "working_out" not in l.lower())
    return t.strip()
LMSTUDIO = os.environ.get("LMSTUDIO_HOST", "http://localhost:1234")


def _post(url: str, payload: dict, headers: dict, timeout: int = 120, retries: int = 1) -> dict:
    """POST JSON, with one short retry on a transient hiccup (429 / 5xx / timeout).

    Free models rate-limit (429) constantly; a single backed-off retry recovers a lot of
    them without much latency. Genuine errors (4xx other than 429) raise immediately so the
    router falls through to the next model/tier.
    """
    import time as _t
    import urllib.error
    data = json.dumps(payload).encode()
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json", **headers})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                _t.sleep(0.4 * (attempt + 1))
                continue
            raise
        except Exception:  # noqa: BLE001 — timeout / connection reset: one retry then bubble up
            if attempt < retries:
                _t.sleep(0.4 * (attempt + 1))
                continue
            raise
    raise RuntimeError("unreachable")  # loop always returns or raises


def _anthropic(model, system, prompt, key):
    out = _post(ENDPOINTS["anthropic"][0],
                {"model": model, "max_tokens": 4096, "system": system,
                 "messages": [{"role": "user", "content": prompt}]},
                {"x-api-key": key, "anthropic-version": "2023-06-01"})
    return out["content"][0]["text"]


def _openai_style(url, model, system, prompt, key):
    out = _post(url, {"model": model, "messages": [
        {"role": "system", "content": system}, {"role": "user", "content": prompt}]},
        {"Authorization": f"Bearer {key}"})
    return out["choices"][0]["message"]["content"]


def _ollama(model, system, prompt):
    out = _post(f"{OLLAMA}/api/chat",
                {"model": model, "stream": False, "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt}]}, {})
    return out["message"]["content"]


_FREE_CACHE: list[str] = []
_FREE_DISK = Path(__file__).resolve().parent / ".free_models_cache.json"
_FREE_TTL = 3600  # 1 hour — the free pool changes slowly; don't refetch every run


def free_models(key: str) -> list[str]:
    """Discover currently-free OpenRouter models. Cached per-process AND to disk (1h TTL),
    so the autonomous loop doesn't hit the models API on every single pulse."""
    if _FREE_CACHE:
        return _FREE_CACHE
    # disk cache: skip the network entirely if a fresh list is on disk
    try:
        import time as _t
        blob = json.loads(_FREE_DISK.read_text(encoding="utf-8"))
        if _t.time() - blob.get("ts", 0) < _FREE_TTL and blob.get("models"):
            _FREE_CACHE.extend(blob["models"])
            return _FREE_CACHE
    except Exception:  # noqa: BLE001 — no/old/bad cache: fetch fresh below
        pass
    try:
        req = urllib.request.Request("https://openrouter.ai/api/v1/models",
                                     headers={"Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())["data"]
        # Skip non-text models (audio/music/image/video) — they leak junk like
        # timestamp tags into drafts. We only want free CHAT models.
        _nontext = ("lyria", "clip", "whisper", "tts", "image", "dall", "sora",
                    "video", "audio", "music", "embed", "vision-only")
        found = sorted(
            m["id"] for m in data
            if (m["id"].endswith(":free")
                or (m.get("pricing", {}).get("prompt") in ("0", 0)
                    and m.get("pricing", {}).get("completion") in ("0", 0)))
            and not any(k in m["id"].lower() for k in _nontext))
        # Rank the BIG free models first — the $0 autonomous loop should think with the
        # strongest brain available, not whatever sorts alphabetically. (Verified 2026-07:
        # nvidia/nemotron-3-ultra-550b-a55b:free is a frontier-class 550B, free and fast.)
        _PREFER = ("nemotron-3-ultra", "nemotron-3-super", "gpt-oss-120b",
                   "gemma-4-31b", "ling-3.0", "gpt-oss-20b")
        def _rank(mid: str) -> int:
            low = mid.lower()
            for i, p in enumerate(_PREFER):
                if p in low:
                    return i
            return len(_PREFER)
        _FREE_CACHE.extend(sorted(found, key=lambda m: (_rank(m), m)))
        try:  # persist for the next run (1h TTL)
            import time as _t
            _FREE_DISK.write_text(json.dumps({"ts": _t.time(), "models": _FREE_CACHE}),
                                  encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    except Exception:  # noqa: BLE001
        pass
    return _FREE_CACHE


def _sonic_url() -> str:
    """Normalize MINDBOT_SONIC_URL to the chat-completions endpoint.

    Accepts the bare Modal URL, the /v1 base, or the full path — all resolve to
    <base>/v1/chat/completions. S0N1C is our own DiffusionGemma served on Modal
    (modal/sonic_diffusiongemma.py): an OpenAI-compatible diffusion LLM.
    """
    # Cost guard: the autonomous 15-min loop sets MINDBOT_NO_SONIC=1 so it stays on
    # free models / CPU and never wakes the (billed) GPU. Flip it off for GPU bursts.
    if os.environ.get("MINDBOT_NO_SONIC"):
        return ""
    u = os.environ.get("MINDBOT_SONIC_URL", "").strip().rstrip("/")
    if not u:
        return ""
    if u.endswith("/chat/completions"):
        return u
    if u.endswith("/v1"):
        return u + "/chat/completions"
    return u + "/v1/chat/completions"


# Models that mean "use S0N1C". diffusion-gemma points here once the endpoint is up.
SONIC_MODELS = {"sonic", "diffusion-gemma", "diffusiongemma"}


def llm(provider: str, model: str, system: str, prompt: str,
        mod: str | None = None, mod_cap: float | None = None) -> tuple[str, str]:
    """Budget-gated entry point. THE chokepoint — core, council, firm, swarm, evolve and every
    third-party mod route through here, so the ceiling cannot be bypassed.

    On a breach we do NOT raise: the framework's contract is that llm() never raises, so the
    autonomous loop keeps doing mechanical work instead of crashing at 3am. It returns
    mode="budget" with a [NEED: ...] marker — visible, honest, and already ledgered by the
    governor. (ModAPI.ask lets the exception through instead, so a mod fails loudly.)
    """
    from . import budget
    try:
        budget.check(model, len(system) + len(prompt), mod=mod, mod_cap=mod_cap)
    except budget.BudgetExceeded as e:
        return (f"<SOLUTION>[NEED: budget] {e}</SOLUTION>", "budget")
    text, mode = _llm_call(provider, model, system, prompt)
    # Modes that cost NOTHING per token must not consume the metered budget:
    #   template/budget — no call happened at all
    #   modal:…/sonic   — an endpoint WE host. It is fixed cost against prepaid credits, so
    #                     billing it at the counselor's OpenRouter rate is simply wrong. Left
    #                     unfixed, running the council on your own GPU would exhaust a spend
    #                     ceiling that protects an account you never touched — and then fall
    #                     back to template mode while the endpoint sat idle and available.
    #   *:free          — free-tier slugs price to $0 anyway, but skipping is cheaper.
    free_mode = (mode in ("template", "budget")
                 or mode.startswith(("modal:", "sonic"))
                 or mode.endswith(":free"))
    if not free_mode:
        # bill the actual reply length, not the pessimistic pre-flight estimate
        pin, pout = budget.price_of(model)
        cost = (len(system) + len(prompt)) / 4 / 1e6 * pin + len(text) / 4 / 1e6 * pout
        budget.record(model, cost, mod=mod, note=mode)
    return text, mode


def _llm_call(provider: str, model: str, system: str, prompt: str) -> tuple[str, str]:
    """Return (text, mode). mode in {'sonic','openrouter','cloud','local','template'}.

    Fallback order is the contract: MODAL -> S0N1C -> OpenRouter -> direct cloud -> local
    Ollama -> template. Every tier swallows its own failure and falls through, so llm() NEVER
    raises and template mode is always reachable — that guarantee keeps the pulse from stalling.
    """
    # MODAL FIRST when enabled. An endpoint you host is FIXED cost against credits you already
    # bought, so per-token metering does not apply — which makes it strictly cheaper than paid
    # OpenRouter for the same work, and the reason it sits above everything else.
    # Opt-IN via MINDBOT_MODAL=1, because silently routing a whole council at someone's private
    # GPU the moment a URL appears in .env is not a decision this module should make for them.
    if os.environ.get("MINDBOT_MODAL") and not os.environ.get("MINDBOT_NO_SONIC"):
        try:
            from . import modal_endpoint
            if modal_endpoint.configured():
                text = modal_endpoint.chat(system, prompt)
                if text.strip():
                    return text, f"modal:{os.environ.get('MODAL_MODEL', modal_endpoint.DEFAULT_MODEL)}"
        except Exception:  # noqa: BLE001 — cold container, bad token, timeout: fall through
            pass
    # S0N1C first when asked: our own DiffusionGemma on Modal. Set MINDBOT_SONIC_ALL=1
    # to flip the ENTIRE council onto it (a diffusion swarm); or it triggers per-seat
    # whenever a counselor's model is one of SONIC_MODELS. Falls through if unreachable.
    sonic = _sonic_url()
    if sonic and (os.environ.get("MINDBOT_SONIC_ALL") or model in SONIC_MODELS):
        key = os.environ.get("MINDBOT_SONIC_KEY", "sonic")  # vLLM ignores auth unless --api-key set
        try:
            return _openai_style(sonic, "sonic", system, prompt, key), "sonic"
        except Exception:  # noqa: BLE001 — endpoint cold/down, degrade to the usual chain
            pass
    # OpenRouter first: one key, every counselor.
    or_key = os.environ.get("OPENROUTER_API_KEY")

    def _warn_free_override(slug: str) -> None:
        """Say it ONCE per process, and ledger it. Silently ignoring an operator's explicit
        config is its own kind of dishonesty — the override is correct, but it must be visible."""
        if getattr(_warn_free_override, "_said", False):
            return
        _warn_free_override._said = True
        msg = f"MINDBOT_FREE=1 overrides MINDBOT_MODEL={slug} (billable) — using free models"
        try:
            from .logs import get_logger
            get_logger(__name__).warning(msg)
        except Exception:  # noqa: BLE001
            pass
        try:
            from .collaboration import ledger
            ledger("cost_guard", msg, "models")
        except Exception:  # noqa: BLE001 — never let bookkeeping break a model call
            pass

    if or_key:
        # MINDBOT_MODEL pins the ENTIRE council to ONE OpenRouter slug (e.g. z-ai/glm-5.2) —
        # the fastest way to A/B a whole model across every seat. Otherwise each seat uses its
        # role-matched slug (OPENROUTER_SLUGS). Either way the EXACT slug rides in the returned
        # `mode` ("openrouter:<slug>") so the ledger + log always prove which brain acted.
        #
        # SAFETY WINS OVER CONVENIENCE — MINDBOT_FREE now BEATS MINDBOT_MODEL.
        # It used to be the other way round, and that quietly cost real money: a .env
        # containing BOTH `MINDBOT_FREE=1` and `MINDBOT_MODEL=z-ai/glm-5.2` billed every call
        # while displaying a $0-budget guard the operator believed was holding. Measured: $0.46
        # in one short session that was supposed to be free.
        #
        # The failure is asymmetric. Wrongly forcing a FREE model costs one run's quality;
        # wrongly honouring a PAID pin inside an unattended loop costs money that isn't there.
        # A control named FREE that does not guarantee free is worse than no control at all.
        # A pinned model that IS free is honoured — the guard only overrides billable pins.
        override = os.environ.get("MINDBOT_MODEL", "").strip()
        want_free = bool(os.environ.get("MINDBOT_FREE"))
        if override and want_free and not override.endswith(":free"):
            _warn_free_override(override)
            override = ""
        if override:
            slugs = [override]
        else:
            slugs = [OPENROUTER_SLUGS.get(model, model)]
            if want_free:  # $1-budget mode: free models only
                # Try several free models so a single rate-limit (429) rolls to the next
                # instead of dropping the whole task to template mode. Free pool is flaky.
                slugs = free_models(or_key)[:8] or slugs
        for slug in slugs:
            try:
                text = _openai_style(OPENROUTER_URL, slug, system, prompt, or_key)
                return text, f"openrouter:{slug}"  # credit the exact model that answered
            except Exception:  # noqa: BLE001 — try next slug, then direct providers
                continue
    url_key = ENDPOINTS.get(provider)
    if url_key and os.environ.get(url_key[1]):
        key = os.environ[url_key[1]]
        try:
            if provider == "anthropic":
                return _anthropic(model, system, prompt, key), "cloud"
            if provider in ("openai", "xai", "deepseek", "mistral"):
                return _openai_style(url_key[0], model, system, prompt, key), "cloud"
        except Exception as e:  # noqa: BLE001 — any failure falls through to local
            _ = e
    # local fallback (Ollama first; covers 'local'/'ollama' providers natively)
    for local_model in (model, os.environ.get("MINDBOT_LOCAL_MODEL", "qwen3:8b")):
        try:
            return _ollama(local_model, system, prompt), "local"
        except Exception:  # noqa: BLE001
            continue
    # template mode: honest placeholder that downstream code treats as a queued draft.
    # Log it loudly — "no model reachable" is the #1 silent failure of an unattended run.
    from .logs import get_logger
    get_logger("models").warning("no model backend reachable (provider=%s model=%s) — "
                                 "task will be re-queued in template mode", provider, model)
    return (
        "<start_working_out>No model backend reachable this wake; queuing the generative "
        "portion and completing the mechanical portion locally.<end_working_out>\n"
        "<SOLUTION>[NEED: model backend — task queued for next counselor wake with API access]</SOLUTION>",
        "template",
    )
