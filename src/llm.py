import json
import re

import requests

import config

DEFAULT_MODEL = "meta/llama-3.3-70b-instruct"


def chat(messages, model=None, temperature=0, max_tokens=2048):
    """Call an OpenAI-compatible NVIDIA NIM endpoint and return the text reply."""
    api_key = config.NVIDIA_API_KEY
    if not api_key:
        raise RuntimeError("NVIDIA API key is not set.")

    payload = {
        "model": model or config.NVIDIA_MODEL or DEFAULT_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    response = requests.post(
        config.NVIDIA_BASE_URL,
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"] or ""


def parse_json(text):
    if not text:
        return None
    clean = text.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?\s*|```$", "", clean, flags=re.MULTILINE).strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", clean, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
    return None
