"""LLM client for the agent harness.  Routes to OpenRouter using the credential
in the opencode auth store (or $OPENROUTER_API_KEY).  Logs usage to a local file."""
from __future__ import annotations

import datetime as _dt
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.request

AUTH = pathlib.Path.home() / ".local" / "share" / "opencode" / "auth.json"
LOG = pathlib.Path(__file__).resolve().parent / "llm_usage.jsonl"


def key() -> str | None:
    k = os.environ.get("OPENROUTER_API_KEY")
    if k:
        return k.strip()
    try:
        return json.loads(AUTH.read_text())["openrouter"]["key"].strip()
    except Exception:  # noqa: BLE001
        return None


def log(rec: dict) -> None:
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")


def chat(prompt: str, model: str, *, json_mode: bool = True, max_tokens: int = 700,
         temperature: float = 0.0, timeout: int = 180, retries: int = 3) -> str:
    k = key()
    if not k:
        raise SystemExit("no OpenRouter key")
    body = {"model": model, "max_tokens": max_tokens, "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}], "usage": {"include": True}}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    data = json.dumps(body).encode()
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions", data=data,
            headers={"Authorization": f"Bearer {k}", "content-type": "application/json",
                     "HTTP-Referer": "https://localhost/bam-agent-harness",
                     "X-Title": "bam-agent-harness"})
        try:
            r = urllib.request.urlopen(req, timeout=timeout)
            j = json.loads(r.read())
            usage = j.get("usage", {})
            log({"ts": _dt.datetime.now().isoformat(timespec="seconds"), "model": model,
                 "usage": usage, "cost": usage.get("cost")})
            return j["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read()[:160]!r}"
            if e.code in (400, 404) and "response_format" in body:
                body.pop("response_format", None); data = json.dumps(body).encode()
            time.sleep(1.5 * (attempt + 1))
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
            time.sleep(1.5 * (attempt + 1))
    raise SystemExit(f"LLM call failed after {retries} attempts: {last}")


def extract_json(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t)
    m = re.search(r"\{.*\}", t, re.S)
    if not m:
        raise ValueError(f"no JSON object in reply: {text[:160]!r}")
    return json.loads(m.group(0))
