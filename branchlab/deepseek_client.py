"""Minimal, secret-free DeepSeek OpenAI-compatible client for candidate plans."""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Any


API_URL = "https://api.deepseek.com/chat/completions"


@dataclass(frozen=True)
class Completion:
    content: str
    usage: dict[str, Any]
    model: str


def complete_with_usage(
    messages: list[dict[str, str]],
    *,
    model: str = "deepseek-chat",
    temperature: float = 0.0,
    max_tokens: int = 800,
) -> Completion:
    """Call DeepSeek and return content plus provider-reported token usage."""
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set")
    payload = json.dumps(
        {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
    ).encode()
    request = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        body = json.load(response)
    return Completion(
        content=body["choices"][0]["message"]["content"],
        usage=dict(body.get("usage") or {}),
        model=str(body.get("model") or model),
    )


def complete(messages: list[dict[str, str]], *, model: str = "deepseek-chat", temperature: float = 0.0, max_tokens: int = 800) -> str:
    """Call DeepSeek using DEEPSEEK_API_KEY; never persist or print the key."""
    return complete_with_usage(
        messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    ).content
