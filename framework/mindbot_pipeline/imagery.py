"""imagery — image generation for the council. Stdlib only.

OpenRouter serves images on TWO different shapes, and picking the wrong one is why a model can
look "missing" when it is actually fine:

  A) POST /api/v1/images          — a DEDICATED image endpoint. Body: {model, prompt,
                                    aspect_ratio?, n?}. Returns {"data":[{"b64_json": ...}]}.
                                    This is where `microsoft/mai-image-2.5-pro` lives.
  B) POST /api/v1/chat/completions — a CHAT call with "modalities":["image","text"]. The PNG
                                    comes back at choices[0].message.images[0].image_url.url
                                    as a data: URI. This is where the Gemini image models live.

`generate()` tries the requested model on its correct shape, then falls back down FALLBACKS so a
provider rate-limit (Azure 429s MAI often) never leaves the caller empty-handed.

Extend: add a model -> put it in FALLBACKS in preference order and, if it is a dedicated-endpoint
model, add its id to _DEDICATED. See docs/MODEL_LINEUP.md for verified ids + prices.
"""
from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from .logs import get_logger

_log = get_logger("imagery")

# Models served by the dedicated /api/v1/images endpoint (shape A). Everything else = shape B.
_DEDICATED = {"microsoft/mai-image-2.5-pro", "openai/gpt-image-2"}

# Preference order. gpt-image-2 first: strongest prompt adherence of the set, which is what
# matters when the prompt is a character brief rather than a scene — it keeps named details
# (a colour, an object, a species) instead of averaging them away. The Gemini line stays
# underneath because it is fast and rarely rate-limits, so a long batch never dies halfway.
FALLBACKS = [
    "openai/gpt-image-2",
    "microsoft/mai-image-2.5-pro",
    "google/gemini-3.1-flash-image",
    "google/gemini-2.5-flash-image",
]

_IMAGES_URL = "https://openrouter.ai/api/v1/images"
_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"


def _headers(key: str) -> dict:
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json",
            "HTTP-Referer": "https://mindbot.council", "X-Title": "MindBot"}


def _post(url: str, body: dict, key: str, timeout: int = 240) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=_headers(key))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _try_one(model: str, prompt: str, key: str, aspect: str) -> bytes | None:
    """One attempt at one model, on whichever endpoint shape that model uses."""
    if model in _DEDICATED:
        d = _post(_IMAGES_URL, {"model": model, "prompt": prompt, "aspect_ratio": aspect}, key)
        rows = d.get("data") or []
        if rows and rows[0].get("b64_json"):
            return base64.b64decode(rows[0]["b64_json"])
        return None
    d = _post(_CHAT_URL, {"model": model, "modalities": ["image", "text"],
                          "messages": [{"role": "user", "content": prompt}]}, key)
    imgs = (d.get("choices") or [{}])[0].get("message", {}).get("images") or []
    if imgs:
        url = imgs[0]["image_url"]["url"]
        if url.startswith("data:"):
            return base64.b64decode(url.split(",", 1)[1])
    return None


def generate(prompt: str, out: str | Path, key: str, model: str | None = None,
             aspect: str = "16:9", retries: int = 2) -> dict:
    """Generate one image to `out`. Falls back through FALLBACKS on provider errors.

    Returns {ok, model, path, bytes, attempts:[{model, status}]} — never raises for a provider
    failure, so a scene-generation loop can keep going and report what happened.
    """
    order = ([model] if model else []) + [m for m in FALLBACKS if m != model]
    attempts: list[dict] = []
    out = Path(out)
    for m in order:
        for attempt in range(retries):
            try:
                data = _try_one(m, prompt, key, aspect)
                if data:
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_bytes(data)
                    attempts.append({"model": m, "status": "ok"})
                    _log.info("image ok %s -> %s (%dKB)", m, out.name, len(data) // 1024)
                    return {"ok": True, "model": m, "path": str(out),
                            "bytes": len(data), "attempts": attempts}
                attempts.append({"model": m, "status": "no-image-in-response"})
                break
            except urllib.error.HTTPError as e:
                body = e.read().decode()[:120]
                attempts.append({"model": m, "status": f"HTTP {e.code}"})
                _log.warning("image %s HTTP %s: %s", m, e.code, body)
                # 429/5xx are transient (Azure rate-limits MAI a lot) — back off and retry,
                # then fall through to the next model in FALLBACKS.
                if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                    time.sleep(2.5 * (attempt + 1))
                    continue
                break
            except Exception as e:  # noqa: BLE001
                attempts.append({"model": m, "status": type(e).__name__})
                _log.warning("image %s error: %s", m, str(e)[:120])
                break
    return {"ok": False, "model": None, "path": None, "bytes": 0, "attempts": attempts}
