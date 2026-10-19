"""Sentence-aware chunking with page tracking and section headings.

Why not fixed 450-word windows?  all-MiniLM-L6-v2 truncates its input at ~256
word-pieces, so long chunks silently lose their tail.  Chunks here are ~190
words, never split mid-sentence, overlap by ~35 words, may span PDF page
breaks (page_start/page_end are recorded) and remember the nearest heading.
"""
from __future__ import annotations

import re

from . import config as C
from .utils import fingerprint

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'\u2018\u201c\u2022•-])")


def _units(doc: dict) -> list[tuple[str, int | None, str]]:
    """Flatten a document into (text, page, heading) units - one per sentence/line.
    Structured table rows are kept intact and never split mid-row.
    """
    units: list[tuple[str, int | None, str]] = []
    heading = ""
    limit = int(C.CHUNK_WORDS * 1.3)
    for page, text in doc["pages"]:
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("# "):
                heading = line[2:].strip()[:120]
                line = line[2:].strip()
                if not line:
                    continue
            # Keep table rows and structured records intact
            is_structured = " | " in line or (line.count(":") >= 2 and ";" in line)
            if is_structured:
                units.append((line, page, heading))
                continue

            pieces = [line]
            if len(line.split()) > 40:
                pieces = [p.strip() for p in _SENT_SPLIT.split(line) if p.strip()]
            for piece in pieces:
                words = piece.split()
                if len(words) > limit:      # unpunctuated wall of text: hard split
                    step = C.CHUNK_WORDS
                    for i in range(0, len(words), step):
                        units.append((" ".join(words[i:i + step]), page, heading))
                else:
                    units.append((piece, page, heading))
    return units


def chunk_document(doc: dict) -> list[dict]:
    units = _units(doc)
    if not units:
        return []
    target, overlap = C.CHUNK_WORDS, C.CHUNK_OVERLAP_WORDS
    chunks: list[list[tuple[str, int | None, str]]] = []
    cur: list[tuple[str, int | None, str]] = []
    cur_words = 0
    has_new = False            # does `cur` hold units not yet emitted in a chunk?
    for u in units:
        w = len(u[0].split())
        if cur and cur_words + w > target:
            chunks.append(cur)
            # carry the tail of the previous chunk as overlap (at least one unit kept out)
            tail: list[tuple[str, int | None, str]] = []
            tw = 0
            for prev in reversed(cur[1:]):
                pw = len(prev[0].split())
                if tw + pw > overlap:
                    break
                tail.insert(0, prev)
                tw += pw
            cur, cur_words = tail, tw
        cur.append(u)
        cur_words += w
        has_new = True
    if cur and has_new:
        chunks.append(cur)

    # merge a tiny trailing chunk into its predecessor
    if len(chunks) > 1:
        last_words = sum(len(t.split()) for t, _, _ in chunks[-1])
        if last_words < C.MIN_CHUNK_WORDS:
            chunks[-2].extend(u for u in chunks[-1] if u not in chunks[-2])
            chunks.pop()

    n_chunks = len(chunks)
    out: list[dict] = []
    for i, group in enumerate(chunks):
        text = "\n".join(t for t, _, _ in group).strip()
        if len(text.split()) < min(C.MIN_CHUNK_WORDS, 6) and n_chunks > 1:
            continue
        pages = [p for _, p, _ in group if p is not None]
        sec = next((h for _, _, h in group if h), "")
        out.append({
            "chunk_id": f"{doc['doc_id']}-{i:04d}",
            "doc_id": doc["doc_id"],
            "chunk_index": i,
            "total_chunks": n_chunks,
            "prev_chunk_id": f"{doc['doc_id']}-{i-1:04d}" if i > 0 else None,
            "next_chunk_id": f"{doc['doc_id']}-{i+1:04d}" if i + 1 < n_chunks else None,
            "text": text,
            "category": doc["category"],
            "title": doc["title"],
            "section": sec,
            "source_url": doc["url"],
            "source_type": doc["source_type"],
            "page": min(pages) if pages else None,
            "page_end": max(pages) if pages else None,
            "priority": doc.get("priority", 2),
            "academic_year": doc.get("academic_year"),
            "fetched_at": doc.get("fetched_at"),
            "n_words": len(text.split()),
            "is_table": bool(" | " in text or (text.count(":") >= 2 and ";" in text)),
        })
    return out


def build_chunks(docs: list[dict]) -> list[dict]:
    """Chunk every document and drop duplicate chunks across the corpus."""
    seen: set[str] = set()
    result: list[dict] = []
    for doc in docs:
        try:
            for ch in chunk_document(doc):
                fp = fingerprint(ch["text"])
                if fp in seen:
                    continue
                seen.add(fp)
                result.append(ch)
        except Exception:  # one bad document must not break the pipeline
            continue
    return result
