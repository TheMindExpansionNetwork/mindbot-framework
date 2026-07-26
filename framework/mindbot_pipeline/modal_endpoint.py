"""MODAL — talk to a private inference server you host yourself.

WHY THIS MODULE EXISTS
  OpenRouter is convenient and metered. A Modal endpoint you own is the opposite: fixed cost,
  your weights, your hardware, and — critically for this project — a model that accepts IMAGES
  and AUDIO, which none of the council's text-only routing could use.

  `thinkingmachines/Inkling-NVFP4`: 975B total / 41B active sparse MoE, 66 layers, 6-of-256
  expert routing. Text + image + audio IN, text OUT. NVFP4-quantised.

AUTHENTICATION — THE PART THAT COSTS AN HOUR IF NOBODY WRITES IT DOWN
  A deployed endpoint sits behind Modal's proxy, which accepts EITHER shape:

      Modal-Key: wk-<id>                                    <-- documented default
      Modal-Secret: ws-<secret>
  or  Authorization: Bearer wk-<id>.ws-<secret>             <-- dot-joined, single header

  We send the documented header pair and fall back to the bearer form, because a proxy that
  advertises both should be taken at its word rather than guessed at.

  THE TRAP: MODAL HAS TWO KINDS OF TOKEN AND ONLY ONE WORKS HERE.

      ak-… / as-…   CLI + account tokens (`modal token set`) — deploy, delete, full account
      wk-… / ws-…   PROXY tokens — the ONLY kind an endpoint accepts

  They look interchangeable and are not. Passing an `ak-` token yields the wonderfully clear
  `{"error":"Webhook token not found: ak-…"}`, which `diagnose()` translates into the actual
  fix. Create the right kind with:

      modal workspace proxy-tokens create

  The secret is shown ONCE at creation and cannot be retrieved later.

  Probed live 2026-07-25 — every failure mode gives a DIFFERENT error, which is why
  `diagnose()` is worth having instead of staring at a bare 401:

      Modal-Key/Secret with ak-…      -> "Webhook token not found: ak-…"   (wrong token TYPE)
      Authorization: Bearer <secret>  -> "proxy auth required: … supply as Bearer wk-<id>.ws-<secret>"
      Authorization: Bearer wk-….ws-… -> "invalid token"      (right shape, dead credentials)
      any header, wrong hostname      -> 503 with an EMPTY body

  THAT LAST ONE IS THE TRAP. Modal serves `*.modal.direct` off a wildcard, so a hostname that
  was never deployed — or was orphaned by a redeploy — still resolves and still answers. It
  returns 503 with no body, which looks exactly like a scale-to-zero container waking up.
  Measured: a URL guessed from the endpoint NAME returned 503 in all five routing regions,
  and polling it for two minutes never warmed it, because there was nothing behind it.

  So a 401 means "real endpoint, bad credentials" and is GOOD NEWS; a bodiless 503 that never
  resolves means the URL itself is wrong. Do not tune tokens against a 503.

GETTING THE RIGHT URL
  Modal Endpoints (`modal endpoint create`) are a managed product, separate from Apps — they do
  NOT appear in `modal app list`, which is its own hour-long red herring. As of CLI 1.5.3,
  `modal endpoint list [--json]` reports name/id/status but NOT the URL. The URL is not
  derivable from the name or the id; take it from the dashboard:

      https://modal.com/endpoints  ->  click the endpoint  ->  copy its URL, append /v1

CONFIG
    MODAL_ENDPOINT_URL        https://<app>--<fn>.<region>.modal.direct/v1
    MODAL_PROXY_TOKEN_ID      wk-…
    MODAL_PROXY_TOKEN_SECRET  ws-…
    MODAL_MODEL               thinkingmachines/Inkling-NVFP4   (default)
"""
from __future__ import annotations

import base64
import json
import mimetypes
import re
import time
import os
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_MODEL = "thinkingmachines/Inkling-NVFP4"
# Cold starts on a 975B MoE are genuinely slow — a stingy timeout looks like an outage.
TIMEOUT = 300


def configured() -> bool:
    return bool(os.environ.get("MODAL_ENDPOINT_URL")
                and os.environ.get("MODAL_PROXY_TOKEN_ID")
                and os.environ.get("MODAL_PROXY_TOKEN_SECRET"))


def _base() -> str:
    return os.environ.get("MODAL_ENDPOINT_URL", "").rstrip("/")


def _headers(bearer: bool = False) -> dict:  # noqa: D401 — see _AUTH note below
    """See `_WORKING_HEADER_SHAPE`. Default is the documented pair PLUS a dummy bearer."""
    return _auth_headers(bearer)


# THE ANSWER, AFTER AN HOUR OF PROBING THE WRONG PATH.
#
# `/v1/models` on this endpoint returns 401 for EVERY auth shape — including `modal curl`,
# which authenticates with Modal's own API credentials. `/v1/chat/completions` with the exact
# same headers returns 200 in 0.6s.
#
# So the models-listing route is gated separately from inference. Health-checking with
# `/v1/models` — the obvious choice, and what this module did first — reports a perfectly
# working endpoint as dead, and sends you off tuning tokens that were never the problem.
# Never health-check an inference endpoint on a route you do not intend to use.
#
# The working shape is all three headers together:
#     Modal-Key: wk-…          proxy auth
#     Modal-Secret: ws-…       proxy auth
#     Authorization: Bearer unused    consumed by the server behind the proxy
_WORKING_HEADER_SHAPE = "Modal-Key + Modal-Secret + Authorization: Bearer unused"


def _auth_headers(bearer: bool = False) -> dict:
    tid = os.environ["MODAL_PROXY_TOKEN_ID"]
    sec = os.environ["MODAL_PROXY_TOKEN_SECRET"]
    h = {"Content-Type": "application/json",
         "Modal-Key": tid, "Modal-Secret": sec,
         # vLLM behind the proxy wants SOME bearer; the value is irrelevant but the header
         # is not. Omit it and you get "missing or invalid Authorization header".
         "Authorization": "Bearer unused"}
    if bearer:                        # fallback: proxy token as a dot-joined bearer instead
        h["Authorization"] = f"Bearer {tid}.{sec}"
    return h




def _post(path: str, payload: dict) -> dict:
    """POST with the documented header pair; retry once with the bearer form on 401.

    Costs one wasted round-trip in the failure case and saves every user from having to know
    which shape their particular endpoint was configured for.
    """
    body = json.dumps(payload).encode("utf-8")
    last: Exception | None = None
    for bearer in (False, True):
        # TRANSIENT DNS/SOCKET FAILURES GET RETRIED. Measured on this machine: an entire
        # 6-frame batch died on `getaddrinfo failed` mid-run — root cause was Tailscale
        # (interface metric 5, below Wi-Fi's 35) intercepting DNS and flapping. The network
        # fix is `tailscale set --accept-dns=false`, but a long unattended job must not lose a
        # whole run to a resolver hiccup either way. HTTP errors are NOT retried here: a 401 or
        # 400 will fail identically the second time and retrying just doubles the latency.
        for attempt in range(3):
            req = urllib.request.Request(_base() + path, data=body,
                                         headers=_headers(bearer), method="POST")
            try:
                with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code != 401 or bearer:
                    raise
                last = e
                break                       # wrong auth shape: switch shape, don't retry
            except (urllib.error.URLError, OSError) as e:
                last = e
                if attempt == 2:
                    break
                time.sleep(1.5 * (attempt + 1))   # 1.5s, 3s
    raise last if last else RuntimeError("request failed with no exception recorded")


# ─────────────────────────────────────────────────────────── multimodal parts

def _data_uri(path: str | Path) -> str:
    """Inline a local file as a data: URI.

    Inlining rather than uploading is deliberate: a URL would require the endpoint to reach
    back out to the public internet to fetch your file, which is both slower and a data-egress
    path this project would then have to justify.
    """
    p = Path(path)
    mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


def _content(prompt: str, images=None, audio=None) -> list | str:
    """Build an OpenAI-style multimodal content array. Plain string when text-only.

    Sending `[{"type":"text",...}]` for a text-only prompt technically works but trips some
    servers' fast paths, so we keep the simple shape when there is nothing to attach.
    """
    if not images and not audio:
        return prompt
    parts: list[dict] = [{"type": "text", "text": prompt}]
    for img in images or []:
        url = img if str(img).startswith(("http://", "https://", "data:")) else _data_uri(img)
        parts.append({"type": "image_url", "image_url": {"url": url}})
    for aud in audio or []:
        # `audio_url` with a data: URI — NOT OpenAI's `input_audio`.
        # Probed live: `input_audio` returns HTTP 400 with 25 pydantic validation errors,
        # because vLLM's OpenAI shim models audio on the same URL-shaped path as images.
        # `audio_url` transcribed a 16kHz WAV verbatim, apostrophes and hyphens intact.
        p = Path(aud)
        mime = mimetypes.guess_type(p.name)[0] or "audio/wav"
        url = str(aud) if str(aud).startswith(("http://", "https://", "data:")) else \
            f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"
        parts.append({"type": "audio_url", "audio_url": {"url": url}})
    return parts


# ───────────────────────────────────────────────────────────────── the calls

                                                        # noqa: E301
# REASONING MODELS EAT THE TOKEN BUDGET BEFORE THEY WRITE A WORD.
# Inkling emits chain-of-thought into a separate `reasoning_content` field, and those tokens
# count against max_tokens. Measured: a studio `implement` stage at max_tokens=2048 returned
# ZERO characters of content — reasoning consumed the entire allowance, so the answer never
# started. It looked like the endpoint was broken; it was the ceiling being too low.
# 8192 leaves room to think AND answer. Override per call when you need more.
DEFAULT_MAX_TOKENS = 8192


def chat(system: str, prompt: str, images=None, audio=None, model: str = "",
         schema: dict | None = None, temperature: float = 0.3,
         max_tokens: int = DEFAULT_MAX_TOKENS, effort: str = "",
         _retry: bool = True) -> str:
    """One completion. Optionally with images, audio, and a strict JSON schema.

    `schema` uses the server's `json_schema` response_format with strict=True, which is the
    reliable way to get parseable output — far better than asking politely and regexing.
    """
    payload = {
        "model": model or os.environ.get("MODAL_MODEL", DEFAULT_MODEL),
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": _content(prompt, images, audio)}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "top_p": 0.9,
    }
    if schema:
        payload["response_format"] = {"type": "json_schema", "json_schema": {
            "name": schema.get("name", "output"), "strict": True,
            "schema": schema.get("schema", schema)}}
    if effort:
        payload["reasoning_effort"] = effort
    out = _post("/chat/completions", payload)
    msg = out["choices"][0]["message"]
    content = (msg.get("content") or "").strip()

    # Inkling returns chain-of-thought in a SEPARATE `reasoning_content` field and the answer
    # in `content`. Falling back to reasoning when content is empty is right for prose — but
    # WRONG when a schema was requested, because reasoning is never valid JSON. Measured: a
    # truncated schema reply left content as a bare "{", the caller fell back to reasoning, and
    # "The user wants me to review a security camera frame…" was stored as an observation.
    if schema:
        # Salvage the object if the model wrapped it in prose or a fence.
        if not content.startswith("{"):
            m = re.search(r"\{.*\}", content, re.S)
            if m:
                content = m.group(0)
        # VALIDATE, don't just look at the first character. Measured: the server returned
        # '{\n\n\n"notable": false' — starts with "{", passes a naive check, and blows up in the
        # caller's json.loads. Reasoning tokens are spent before the object is written, so a
        # long prompt can truncate the JSON while `finish_reason` still reads "stop".
        try:
            json.loads(content)
            return content
        except json.JSONDecodeError:
            pass
        if _retry:
            # Self-heal ONCE with a much larger ceiling rather than making every caller guess.
            # Cheap insurance: this only fires on the truncation path, never on the happy one.
            return chat(system, prompt, images=images, audio=audio, model=model, schema=schema,
                        temperature=temperature, max_tokens=max_tokens * 3, effort=effort,
                        _retry=False)
        raise ValueError(
            f"schema output did not parse even at max_tokens={max_tokens}. Reasoning likely "
            f"consumed the budget before the JSON was written. Got: {content[:120]!r}")
    return content or (msg.get("reasoning_content") or "").strip()


def describe_image(path, question: str = "Describe this image precisely.") -> str:
    return chat("You are a precise visual analyst.", question, images=[path])


def transcribe(path, instruction: str = "Transcribe this audio verbatim.") -> str:
    return chat("You are a precise transcriptionist.", instruction, audio=[path])


def models() -> list[str]:
    last = None
    for bearer in (False, True):
        req = urllib.request.Request(_base() + "/models", headers=_headers(bearer))
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return [m["id"] for m in json.loads(r.read().decode()).get("data", [])]
        except urllib.error.HTTPError as e:
            last = e
            if e.code != 401:
                raise
    raise last


# ──────────────────────────────────────────────────────────────── diagnosis

def probe(url: str = "", tid: str = "", sec: str = "") -> dict:
    """Run the full auth elimination matrix and return a report you can hand to support.

    Written after doing this by hand for an hour. Modal's proxy returns a DIFFERENT error for
    every distinct failure, and the pattern across the matrix is what identifies the fault:

        "proxy auth required: …"                 the header FORMAT was not recognised
        "invalid token"                          format recognised, credentials rejected
        "missing or invalid Authorization header" this shape is not accepted by this endpoint
        503 with an empty body                   nothing behind that hostname (wildcard DNS)
        200                                      done

    The decisive case is `bearer-dot` returning "invalid token" while the token was minted
    minutes earlier in the same workspace: that combination eliminates format, token type,
    token age, region and hostname, and leaves only an endpoint-side configuration fault. No
    amount of client-side fiddling fixes that one, which is exactly why it is worth being able
    to prove it in one command rather than arguing about it.
    """
    url = (url or _base()).rstrip("/")
    tid = tid or os.environ.get("MODAL_PROXY_TOKEN_ID", "")
    sec = sec or os.environ.get("MODAL_PROXY_TOKEN_SECRET", "")
    if not url.endswith("/v1"):
        url += "/v1"

    # ORDER MATTERS: `pair+dummy` is the shape that actually works, so it goes first and the
    # loop stops there. The others exist to characterise a failure, not to be tried hopefully.
    shapes = {
        "pair+dummy":   {"Modal-Key": tid, "Modal-Secret": sec, "Authorization": "Bearer unused"},
        "header-pair":  {"Modal-Key": tid, "Modal-Secret": sec},
        "bearer-dot":   {"Authorization": f"Bearer {tid}.{sec}"},
        "no-auth":      {},
    }
    # Probe INFERENCE, not /v1/models. On this endpoint the listing route 401s for every auth
    # shape (including `modal curl`) while chat/completions returns 200 with identical headers.
    # Probing the listing route declared a working endpoint dead for an hour.
    body_json = json.dumps({"model": os.environ.get("MODAL_MODEL", DEFAULT_MODEL),
                            "messages": [{"role": "user", "content": "ok"}],
                            "max_tokens": 8}).encode("utf-8")
    rows = []
    for name, h in shapes.items():
        try:
            req = urllib.request.Request(url + "/chat/completions", data=body_json,
                                         headers={**h, "Content-Type": "application/json"},
                                         method="POST")
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                rows.append({"shape": name, "code": r.status, "body": "OK", "verdict": "WORKS"})
                break
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="ignore")[:90].strip()
            if e.code == 503 and not body:
                v = "wrong hostname — wildcard DNS, nothing behind it"
            elif "proxy auth required" in body:
                v = "format not recognised"
            elif "invalid token" in body:
                v = "format OK, credentials rejected"
            elif "Webhook token not found" in body:
                v = "wrong token TYPE (ak-/as- is a CLI token)"
            elif "Authorization header" in body:
                v = "this shape not accepted here"
            else:
                v = "unclassified"
            rows.append({"shape": name, "code": e.code, "body": body, "verdict": v})
        except Exception as e:  # noqa: BLE001
            rows.append({"shape": name, "code": type(e).__name__, "body": str(e)[:90],
                         "verdict": "network/timeout"})

    works = any(r["verdict"] == "WORKS" for r in rows)
    fmt_ok = any("credentials rejected" in r["verdict"] for r in rows)
    dead = all("wrong hostname" in r["verdict"] for r in rows)
    if works:
        conclusion = "endpoint reachable and authenticated."
    elif dead:
        conclusion = ("Nothing is behind this hostname. Get the real URL from "
                      "https://modal.com/endpoints (the CLI does not print it).")
    elif fmt_ok:
        conclusion = ("The header format is correct and the token is being REJECTED. If this "
                      "token was just created in this workspace (modal workspace proxy-tokens "
                      "create) then every client-side variable is eliminated — format, token "
                      "type, age, region and hostname — and the fault is endpoint-side. Compare "
                      "against the dashboard's own 'call this endpoint' snippet, or ask support "
                      "why workspace-scoped proxy tokens are refused by this endpoint.")
    else:
        conclusion = "No shape was accepted. Check the URL first, then the token type."
    return {"url": url, "token_id": tid[:12] + "…" if tid else "(none)",
            "rows": rows, "works": works, "conclusion": conclusion}


def diagnose() -> dict:
    """Say WHICH thing is wrong, not just that something is.

    A bare 401 is nearly useless — wrong header shape, wrong credentials, and a sleeping
    container all look identical. These three cases have distinct fixes, so they get distinct
    messages.
    """
    if not configured():
        missing = [k for k in ("MODAL_ENDPOINT_URL", "MODAL_PROXY_TOKEN_ID",
                               "MODAL_PROXY_TOKEN_SECRET") if not os.environ.get(k)]
        return {"ok": False, "problem": "not configured", "missing": missing,
                "fix": "set these in framework/.env — see .env.example"}
    try:
        # Health-check via INFERENCE, not /v1/models. On this endpoint the models-listing route
        # is gated separately and 401s for every auth shape (including `modal curl`), while
        # chat/completions with identical headers returns 200. Probing /v1/models reported a
        # working endpoint as dead for an hour.
        import time as _t
        t0 = _t.time()
        txt = chat("You are terse.", "Reply with the single word: ok", max_tokens=64)
        return {"ok": True,
                "note": f"reachable in {_t.time() - t0:.1f}s via chat/completions "
                        f"— replied {txt.strip()[:40]!r} "
                        f"(model: {os.environ.get('MODAL_MODEL', DEFAULT_MODEL)})"}
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore")[:200]
        tid = os.environ.get("MODAL_PROXY_TOKEN_ID", "")
        # THE MOST COMMON MISTAKE, AND THE MOST CONFUSING: Modal issues two token families
        # that look alike. `ak-`/`as-` are CLI+account tokens (deploy, delete, full account);
        # only `wk-`/`ws-` proxy tokens open an endpoint. Catch it on the prefix too, so the
        # advice is right even when the server's wording changes.
        if "Webhook token not found" in body or tid.startswith("ak-"):
            return {"ok": False, "problem": "wrong token TYPE", "detail": body,
                    "fix": "that is a CLI/account token (ak-…/as-…), not a proxy token. "
                           "Endpoints only accept wk-…/ws-… — create one with: "
                           "modal workspace proxy-tokens create   (the secret is shown ONCE)"}
        if e.code == 401 and "proxy auth required" in body:
            return {"ok": False, "problem": "wrong header format", "detail": body,
                    "fix": "send Modal-Key/Modal-Secret, or Authorization: Bearer wk-<id>.ws-<secret>"}
        if e.code == 401:
            return {"ok": False, "problem": "credentials rejected", "detail": body,
                    "fix": "the shape is right but the token is not valid — mistyped, expired, "
                           "or revoked. Re-copy it from the Modal dashboard, and never "
                           "transcribe a token by ear."}
        if e.code == 503:
            # A bodiless 503 is a WRONG HOSTNAME, not a cold start. Modal answers every
            # *.modal.direct name off a wildcard, so an orphaned or never-deployed host still
            # resolves and returns this forever. Polling it looks productive and never is.
            return {"ok": False, "problem": "wrong URL (nothing behind that hostname)",
                    "detail": f"503, empty body — {body!r}",
                    "fix": "*.modal.direct answers on a wildcard, so a dead host still 503s and "
                           "never warms up. Get the real URL from https://modal.com/endpoints "
                           "(click the endpoint) and append /v1. Note that `modal endpoint list` "
                           "does not print URLs, and Endpoints do not appear in `modal app list`."}
        if e.code == 404:
            return {"ok": False, "problem": "no such endpoint", "detail": body,
                    "fix": "check MODAL_ENDPOINT_URL ends with /v1 and the endpoint is live"}
        return {"ok": False, "problem": f"HTTP {e.code}", "detail": body, "fix": ""}
    except Exception as e:  # noqa: BLE001 — timeouts, DNS, TLS
        return {"ok": False, "problem": type(e).__name__, "detail": str(e)[:200],
                "fix": "a cold 975B MoE can take minutes to wake; retry once before digging"}
