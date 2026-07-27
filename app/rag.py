"""Small, deterministic local RAG index with transparent citations.

The index intentionally uses hashed term vectors so it runs on a free-tier host
without downloading a model. Swap `embed` for a sentence-transformer encoder for
a semantic-production variant; the persisted format and MCP tool stay unchanged.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .settings import INDEX_PATH, POLICY_DIR

DIMENSIONS = 256
TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9'-]{1,}")


def _tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def embed(text: str) -> list[float]:
    """Stable feature-hash embedding; no network or API key required."""
    counts = Counter(_tokens(text))
    vector = [0.0] * DIMENSIONS
    for token, count in counts.items():
        bucket = int(hashlib.sha256(token.encode()).hexdigest(), 16) % DIMENSIONS
        vector[bucket] += 1 + math.log(count)
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [round(v / norm, 7) for v in vector]


def _chunk_markdown(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    title = path.stem.replace("_", " ").title()
    section = "Overview"
    buffer: list[str] = []
    chunks: list[dict[str, str]] = []
    for line in text.splitlines():
        if line.startswith("#"):
            if buffer:
                chunks.append({"title": title, "section": section, "text": "\n".join(buffer).strip()})
                buffer = []
            section = line.lstrip("# ").strip()
        else:
            buffer.append(line)
    if buffer:
        chunks.append({"title": title, "section": section, "text": "\n".join(buffer).strip()})
    # Limit chunks to roughly 220 words with a small overlap.
    split: list[dict[str, str]] = []
    for chunk in chunks:
        words = chunk["text"].split()
        for start in range(0, max(len(words), 1), 190):
            part = words[start : start + 220]
            if part:
                split.append({**chunk, "text": " ".join(part)})
            if start + 220 >= len(words):
                break
    return split


def build_index() -> dict[str, Any]:
    records = []
    for path in sorted(POLICY_DIR.glob("*.md")):
        for number, chunk in enumerate(_chunk_markdown(path), start=1):
            records.append({
                "id": f"{path.stem}-{number}", "document": path.name,
                **chunk, "embedding": embed(chunk["text"]),
            })
    index = {"version": 1, "embedding": "stable-hash-256", "chunks": records}
    INDEX_PATH.write_text(json.dumps(index, indent=2), encoding="utf-8")
    return index


def load_index() -> dict[str, Any]:
    return json.loads(INDEX_PATH.read_text()) if INDEX_PATH.exists() else build_index()


def search(query: str, limit: int = 4) -> list[dict[str, Any]]:
    query_vector = embed(query)
    matches = []
    for item in load_index()["chunks"]:
        score = sum(a * b for a, b in zip(query_vector, item["embedding"]))
        matches.append({k: v for k, v in item.items() if k != "embedding"} | {"score": round(score, 3)})
    return sorted(matches, key=lambda result: result["score"], reverse=True)[:limit]
