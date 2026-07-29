"""Small, deterministic local RAG index with transparent citations.

Three source formats are supported — Markdown, HTML, and plain text — because the
policy corpus is authored in the format that suits each document. All three are
parsed heading-aware so that every chunk carries the section heading it came
from, which is what makes a citation useful to a reader.

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
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from .settings import INDEX_PATH, POLICY_DIR

# A large hashing space keeps collisions rare across the full corpus. Vectors are
# stored sparsely (bucket -> weight), so dimensionality costs nothing on disk.
DIMENSIONS = 2 ** 18
TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9'-]{1,}")

# Document title and section heading are strong topical signals. They are counted
# extra so that a query such as "security requirements" can retrieve a relevant
# section even when the body uses more specific wording than the query.
HEADING_WEIGHT = 3

# A token is "distinctive" when it is rare enough across the corpus to carry
# topic information. Corpus-wide filler ("the", "employee", "policy") falls below.
DISTINCTIVE_IDF_FLOOR = 2.0

# Chunking is a fixed word window with overlap so the index is byte-reproducible.
CHUNK_WORDS = 220
CHUNK_STRIDE = 190

SUPPORTED_SUFFIXES = (".md", ".html", ".txt")

# A plain-text heading is a short, fully upper-case line — the convention used by
# the .txt documents in the corpus.
TXT_HEADING_RE = re.compile(r"^[A-Z][A-Z0-9 ,.'&/()-]{3,}$")


def _tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def _bucket(token: str) -> int:
    return int(hashlib.sha256(token.encode()).hexdigest(), 16) % DIMENSIONS


def build_idf(texts: list[str]) -> dict[str, float]:
    """Inverse document frequency per token, keyed by hash bucket.

    Without this weighting, tokens that appear in nearly every policy document
    ("employee", "policy", "company") dominate every vector and retrieval
    collapses towards whichever chunk is longest. Storing the weights in the
    index keeps query-time and index-time scoring identical.
    """
    total = len(texts) or 1
    frequency: Counter[int] = Counter()
    for text in texts:
        frequency.update({_bucket(token) for token in _tokens(text)})
    return {str(bucket): math.log((total + 1) / (count + 1)) + 1.0 for bucket, count in frequency.items()}


def embed(text: str, idf: dict[str, float] | None = None, heading: str = "") -> dict[str, float]:
    """Stable IDF-weighted sparse feature-hash embedding.

    Returned as a ``{bucket: weight}`` mapping of non-zero components only. No
    network access and no API key are required, and the result is byte-identical
    across runs and machines.
    """
    counts = Counter(_tokens(text))
    if heading:
        for token in _tokens(heading):
            counts[token] += HEADING_WEIGHT

    vector: dict[str, float] = {}
    for token, count in counts.items():
        bucket = str(_bucket(token))
        weight = 1.0 if idf is None else idf.get(bucket, 1.0)
        vector[bucket] = vector.get(bucket, 0.0) + (1 + math.log(count)) * weight

    norm = math.sqrt(sum(value * value for value in vector.values())) or 1.0
    return {bucket: round(value / norm, 6) for bucket, value in vector.items()}


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    """Dot product of two L2-normalised sparse vectors."""
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(bucket, 0.0) for bucket, value in left.items())


def distinctive_tokens(text: str, idf: dict[str, float] | None, floor: float = DISTINCTIVE_IDF_FLOOR) -> set[str]:
    """Query tokens carrying real topical signal, i.e. not corpus-wide filler.

    Cosine similarity alone cannot separate an in-corpus question from an
    out-of-corpus one: a short off-topic question normalises to a small vector
    that can still align with a long chunk by accident. Counting how many of the
    caller's *distinctive* words actually occur in a chunk is a far cleaner
    signal, and it is what the refusal guardrail keys on.
    """
    if idf is None:
        return set(_tokens(text))
    # A token the corpus has never seen is maximally distinctive, so it defaults
    # to infinity rather than zero — it is precisely the evidence that a question
    # is out of scope, and must not be filtered out of the check.
    return {token for token in _tokens(text) if idf.get(str(_bucket(token)), math.inf) >= floor}


class _HeadingAwareHTMLParser(HTMLParser):
    """Collect HTML body text grouped under the most recent heading."""

    SKIP = {"script", "style", "head"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[tuple[str, str]] = []
        self._section = "Overview"
        self._buffer: list[str] = []
        self._in_heading = False
        self._heading: list[str] = []
        self._skip_depth = 0

    def _flush(self) -> None:
        text = " ".join(" ".join(self._buffer).split())
        if text:
            self.blocks.append((self._section, text))
        self._buffer = []

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag in self.SKIP:
            self._skip_depth += 1
        elif re.fullmatch(r"h[1-6]", tag):
            self._flush()
            self._in_heading = True
            self._heading = []

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif re.fullmatch(r"h[1-6]", tag):
            heading = " ".join(" ".join(self._heading).split())
            if heading:
                self._section = heading
            self._in_heading = False
        elif tag in {"td", "th", "p", "li", "tr"}:
            # Keep cell and list boundaries from fusing into one long word run.
            self._buffer.append(" ")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_heading:
            self._heading.append(data)
        else:
            self._buffer.append(data)

    def close(self) -> None:  # noqa: D102 - inherited behaviour plus a final flush
        super().close()
        self._flush()


def _blocks_from_markdown(text: str) -> list[tuple[str, str]]:
    section = "Overview"
    buffer: list[str] = []
    blocks: list[tuple[str, str]] = []
    for line in text.splitlines():
        if line.startswith("#"):
            if buffer:
                blocks.append((section, "\n".join(buffer).strip()))
                buffer = []
            section = line.lstrip("# ").strip()
        else:
            buffer.append(line)
    if buffer:
        blocks.append((section, "\n".join(buffer).strip()))
    return [(heading, body) for heading, body in blocks if body]


def _blocks_from_html(text: str) -> list[tuple[str, str]]:
    parser = _HeadingAwareHTMLParser()
    parser.feed(text)
    parser.close()
    return parser.blocks


def _blocks_from_text(text: str) -> list[tuple[str, str]]:
    section = "Overview"
    buffer: list[str] = []
    blocks: list[tuple[str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and TXT_HEADING_RE.fullmatch(stripped):
            if buffer:
                blocks.append((section, "\n".join(buffer).strip()))
                buffer = []
            section = stripped.title()
        else:
            buffer.append(line)
    if buffer:
        blocks.append((section, "\n".join(buffer).strip()))
    return [(heading, body) for heading, body in blocks if body]


_PARSERS = {
    ".md": _blocks_from_markdown,
    ".html": _blocks_from_html,
    ".txt": _blocks_from_text,
}


def parse_document(path: Path) -> list[dict[str, str]]:
    """Return heading-aware, window-limited chunks for one policy document."""
    blocks = _PARSERS[path.suffix](path.read_text(encoding="utf-8"))
    title = path.stem.replace("_", " ").title()

    chunks: list[dict[str, str]] = []
    for section, body in blocks:
        words = body.split()
        for start in range(0, max(len(words), 1), CHUNK_STRIDE):
            part = words[start : start + CHUNK_WORDS]
            if part:
                chunks.append({"title": title, "section": section, "text": " ".join(part)})
            if start + CHUNK_WORDS >= len(words):
                break
    return chunks


def source_documents() -> list[Path]:
    """Every indexable policy file, in a stable order."""
    return sorted(p for p in POLICY_DIR.iterdir() if p.suffix in SUPPORTED_SUFFIXES)


def build_index() -> dict[str, Any]:
    # First pass: chunk every document so IDF is computed over the real corpus.
    staged: list[dict[str, str]] = []
    for path in source_documents():
        for number, chunk in enumerate(parse_document(path), start=1):
            staged.append({
                "id": f"{path.stem}-{number}", "document": path.name,
                "format": path.suffix.lstrip("."), **chunk,
            })

    # Include stable document metadata in both IDF and vectors. It is useful
    # retrieval context (for example "data security" or "benefits") rather
    # than a decorative label, and avoids relying only on the prose body.
    idf = build_idf([
        f"{chunk['document']} {chunk['title']} {chunk['section']} {chunk['text']}"
        for chunk in staged
    ])
    records = [
        {
            **chunk,
            "embedding": embed(
                chunk["text"],
                idf,
                heading=f"{chunk['document']} {chunk['title']} {chunk['section']}",
            ),
        }
        for chunk in staged
    ]

    index = {
        "version": 4,
        "embedding": "sparse-hash-idf+document-metadata",
        "idf": idf,
        "chunks": records,
    }
    INDEX_PATH.write_text(json.dumps(index), encoding="utf-8")
    return index


def load_index() -> dict[str, Any]:
    return json.loads(INDEX_PATH.read_text()) if INDEX_PATH.exists() else build_index()


def search(query: str, limit: int = 4) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    index = load_index()
    idf = index.get("idf")
    query_vector = embed(query, idf)
    wanted = distinctive_tokens(query, idf)

    matches = []
    for item in index["chunks"]:
        present = wanted & set(_tokens(
            f"{item['document']} {item['title']} {item['section']} {item['text']}"
        ))
        matches.append(
            {k: v for k, v in item.items() if k != "embedding"}
            | {
                "score": round(cosine(query_vector, item["embedding"]), 3),
                "support": round(len(present) / len(wanted), 3) if wanted else 0.0,
            }
        )
    return sorted(matches, key=lambda result: (-result["support"], -result["score"], result["id"]))[:limit]
