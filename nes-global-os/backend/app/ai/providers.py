"""Provider-independent LLM access over the providers' official HTTP APIs.

Adding a provider = adding one function to ADAPTERS. Keys are passed in by the runtime and never
leave the backend.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

PROVIDERS = {
    "anthropic": {"label": "Anthropic Claude", "default_base": "https://api.anthropic.com"},
    "openai": {"label": "OpenAI", "default_base": "https://api.openai.com"},
    "gemini": {"label": "Google Gemini", "default_base": "https://generativelanguage.googleapis.com"},
    "openai_compatible": {"label": "OpenAI-compatible (self-hosted / other)", "default_base": None},
}

# Tests swap this for an httpx.MockTransport.
transport: httpx.BaseTransport | None = None


class ProviderError(Exception):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind  # auth | quota | unavailable | bad_request | config


@dataclass
class Completion:
    text: str
    input_tokens: int
    output_tokens: int


def _client() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(120, connect=10), transport=transport)


def _raise_for(resp: httpx.Response) -> None:
    if resp.status_code < 400:
        return
    body = resp.text[:500]
    low = body.lower()
    if resp.status_code in (401, 403):
        raise ProviderError("auth", f"HTTP {resp.status_code}: credentials rejected")
    if resp.status_code == 429 or "credit balance" in low or "quota" in low or "insufficient_quota" in low:
        raise ProviderError("quota", f"HTTP {resp.status_code}: quota or rate limit reached")
    if resp.status_code >= 500:
        raise ProviderError("unavailable", f"HTTP {resp.status_code}: provider unavailable")
    raise ProviderError("bad_request", f"HTTP {resp.status_code}: {body}")


def _anthropic(key, base, model, system, user, max_tokens) -> Completion:
    with _client() as c:
        r = c.post(f"{base or PROVIDERS['anthropic']['default_base']}/v1/messages",
                   headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                   json={"model": model, "max_tokens": max_tokens, "system": system,
                         "messages": [{"role": "user", "content": user}]})
    _raise_for(r)
    d = r.json()
    text = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
    u = d.get("usage", {})
    return Completion(text, int(u.get("input_tokens", 0)), int(u.get("output_tokens", 0)))


def _openai(key, base, model, system, user, max_tokens) -> Completion:
    if not base:
        raise ProviderError("config", "No base URL configured")
    with _client() as c:
        r = c.post(f"{base.rstrip('/')}/v1/chat/completions",
                   headers={"authorization": f"Bearer {key}"},
                   json={"model": model, "max_completion_tokens": max_tokens,
                         "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
    _raise_for(r)
    d = r.json()
    u = d.get("usage", {})
    return Completion(d["choices"][0]["message"].get("content") or "",
                      int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0)))


def _gemini(key, base, model, system, user, max_tokens) -> Completion:
    with _client() as c:
        r = c.post(f"{base or PROVIDERS['gemini']['default_base']}/v1beta/models/{model}:generateContent",
                   headers={"x-goog-api-key": key},
                   json={"systemInstruction": {"parts": [{"text": system}]},
                         "contents": [{"role": "user", "parts": [{"text": user}]}],
                         "generationConfig": {"maxOutputTokens": max_tokens}})
    _raise_for(r)
    d = r.json()
    parts = (d.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    u = d.get("usageMetadata", {})
    return Completion("".join(p.get("text", "") for p in parts),
                      int(u.get("promptTokenCount", 0)), int(u.get("candidatesTokenCount", 0)))


ADAPTERS = {
    "anthropic": _anthropic,
    "openai": lambda k, b, *a: _openai(k, b or PROVIDERS["openai"]["default_base"], *a),
    "openai_compatible": _openai,
    "gemini": _gemini,
}


def complete(provider: str, key: str, base_url: str | None, model: str, system: str, user: str,
             max_tokens: int = 1500) -> Completion:
    fn = ADAPTERS.get(provider)
    if not fn:
        raise ProviderError("config", f"Unknown provider {provider}")
    try:
        return fn(key, base_url, model, system, user, max_tokens)
    except httpx.HTTPError as e:
        raise ProviderError("unavailable", f"Network error: {e.__class__.__name__}") from e
