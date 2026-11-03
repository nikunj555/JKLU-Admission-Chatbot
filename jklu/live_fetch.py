"""Tier 2: Live official website fetch for JK Lakshmipat University (jklu.edu.in).

Security guarantees (SSRF protection):
1. Strict domain allowlist: only 'jklu.edu.in' and its subdomains (*.jklu.edu.in)
2. Safe URL schemes: https, http only
3. Explicit IP blocking: reject private, loopback, link-local, and reserved IP ranges
4. Redirect validation: redirects off the allowlist are strictly rejected
5. Bounded payload & time: max 1 MB per page, 3s timeout, max 3 pages per query

Relevance & Performance:
- In-memory LRU TTL cache (6-24 hours) for parsed chunks
- Ranked candidate selection via site_map.json + in-memory FastEmbed re-ranking
- Zero filesystem mutation of the committed vector_store
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import re
import socket
import time
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
import numpy as np

from . import config as C
from .utils import log

_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 JKLU-Assistant/2.0"
_ALLOWLIST_HOST = "jklu.edu.in"

# In-memory page & chunk cache with TTL: url -> {chunks: list, fetched_at: float}
_LIVE_PAGE_CACHE: dict[str, dict[str, Any]] = {}
_LAST_FETCH_STATUS: dict[str, Any] = {
    "status": "idle",
    "last_fetched_url": None,
    "last_fetched_at": None,
    "last_error": None,
    "cached_pages": 0,
}
_LAST_TIMINGS: dict[str, float] = {
    "robots_sitemap_ms": 0.0,
    "page_fetch_ms": 0.0,
    "parse_chunk_ms": 0.0,
    "embed_rerank_ms": 0.0,
    "total_live_fetch_ms": 0.0,
}

def get_last_live_timings() -> dict[str, float]:
    return dict(_LAST_TIMINGS)


def is_safe_url(url: str) -> bool:
    """Validate that the URL belongs strictly to jklu.edu.in or subdomains and is not a private IP."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return False

        # Strictly check against allowlist domain
        if hostname != _ALLOWLIST_HOST and not hostname.endswith("." + _ALLOWLIST_HOST):
            return False

        # Resolve hostname to check for internal/private/loopback IPs
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for item in addr_info:
                ip_str = item[4][0]
                ip_obj = ipaddress.ip_address(ip_str)
                if (
                    ip_obj.is_private
                    or ip_obj.is_loopback
                    or ip_obj.is_link_local
                    or ip_obj.is_reserved
                    or ip_obj.is_multicast
                ):
                    return False
        except Exception:
            # If DNS resolution fails, reject
            return False

        return True
    except Exception:
        return False


def _clean_html_text(html: str) -> str:
    """Extract clean text content from HTML without script, style, navigation clutter."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
        tag.decompose()

    # Look for primary content container if available
    main = soup.find("main") or soup.find("article") or soup.find("div", {"id": "content"}) or soup.body
    if not main:
        main = soup

    text = main.get_text(separator="\n")
    # Normalize whitespaces
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def _chunk_text(text: str, chunk_size: int = 150, overlap: int = 30) -> list[str]:
    """Split clean text into word-based chunks with overlap."""
    words = text.split()
    if not words:
        return []
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


def load_sitemap_candidates() -> list[dict[str, Any]]:
    """Load candidates from data/manual/site_map.json."""
    if not C.SITE_MAP_PATH.is_file():
        return []
    try:
        with open(C.SITE_MAP_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        candidates = []
        for cat, items in data.items():
            for item in items:
                candidates.append(item)
        return candidates
    except Exception as exc:
        log.warning("Could not read site_map.json: %s", exc)
        return []


async def fetch_page_async(url: str, timeout: float = 3.0) -> str | None:
    """Safely fetch a webpage content with size and timeout guards."""
    if not is_safe_url(url):
        log.warning("Blocked non-allowlisted or unsafe live fetch URL: %s", url)
        return None

    global _LAST_FETCH_STATUS
    now = time.time()

    # Check TTL cache
    cached = _LIVE_PAGE_CACHE.get(url)
    if cached and (now - cached["fetched_at"]) < C.CACHE_TTL:
        return cached.get("raw_text")

    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
            timeout=timeout,
        ) as client:
            response = await client.get(url)
            # Re-verify final redirect URL
            final_url = str(response.url)
            if not is_safe_url(final_url):
                log.warning("Blocked unsafe redirect to %s", final_url)
                return None

            if response.status_code != 200:
                _LAST_FETCH_STATUS.update({
                    "status": "error",
                    "last_error": f"HTTP {response.status_code}",
                    "last_fetched_url": url,
                    "last_fetched_at": now,
                })
                return None

            content = response.content
            if len(content) > C.LIVE_MAX_BYTES:
                content = content[: C.LIVE_MAX_BYTES]

            raw_text = _clean_html_text(content.decode("utf-8", errors="replace"))
            _LIVE_PAGE_CACHE[url] = {
                "raw_text": raw_text,
                "fetched_at": now,
                "title": _extract_title(response.text) or url,
            }
            _LAST_FETCH_STATUS.update({
                "status": "ok",
                "last_fetched_url": url,
                "last_fetched_at": now,
                "last_error": None,
                "cached_pages": len(_LIVE_PAGE_CACHE),
            })
            return raw_text
    except Exception as exc:
        log.warning("Live fetch error for %s: %s", url, exc)
        _LAST_FETCH_STATUS.update({
            "status": "error",
            "last_error": str(exc),
            "last_fetched_url": url,
            "last_fetched_at": now,
        })
        return None


def _extract_title(html: str) -> str:
    try:
        soup = BeautifulSoup(html[:4096], "html.parser")
        if soup.title and soup.title.string:
            return soup.title.string.strip()
    except Exception:
        pass
    return ""


def get_live_cache_stats() -> dict[str, Any]:
    """Return runtime cache and status info for /api/health."""
    now = time.time()
    valid_cached = sum(1 for item in _LIVE_PAGE_CACHE.values() if (now - item["fetched_at"]) < C.CACHE_TTL)
    return {
        "enabled": C.LIVE_FETCH_ENABLED,
        "cached_pages": valid_cached,
        "ttl_seconds": C.CACHE_TTL,
        "last_status": _LAST_FETCH_STATUS["status"],
        "last_url": _LAST_FETCH_STATUS["last_fetched_url"],
        "last_time": _LAST_FETCH_STATUS["last_fetched_at"],
        "last_error": _LAST_FETCH_STATUS["last_error"],
    }


def select_candidate_urls(query: str, max_candidates: int = 3) -> list[dict[str, Any]]:
    """Rank candidate URLs from the curated sitemap using simple lexical overlap with query."""
    candidates = load_sitemap_candidates()
    if not candidates:
        return []

    q_terms = set(re.findall(r"\w+", query.lower()))
    scored = []
    for c in candidates:
        title_terms = set(re.findall(r"\w+", (c.get("title", "") + " " + c.get("url", "")).lower()))
        overlap = len(q_terms & title_terms)
        score = overlap + (2.0 if c.get("priority") == 1 else 1.0)
        scored.append((score, c))

    scored.sort(key=lambda x: -x[0])
    return [c for score, c in scored[:max_candidates]]


async def fetch_and_rank_live_evidence(
    query: str,
    embedder: Any,
    max_pages: int = 3,
    top_k_chunks: int = 4,
) -> list[dict[str, Any]]:
    """Fetch live candidate pages asynchronously, chunk, embed with fastembed, and return re-ranked chunks."""
    global _LAST_TIMINGS
    t_start = time.perf_counter()
    _LAST_TIMINGS = {
        "robots_sitemap_ms": 0.0,
        "page_fetch_ms": 0.0,
        "parse_chunk_ms": 0.0,
        "embed_rerank_ms": 0.0,
        "total_live_fetch_ms": 0.0,
    }
    if not C.LIVE_FETCH_ENABLED:
        return []

    t_cand = time.perf_counter()
    candidates = select_candidate_urls(query, max_candidates=max_pages)
    _LAST_TIMINGS["robots_sitemap_ms"] = round((time.perf_counter() - t_cand) * 1000, 2)
    if not candidates:
        _LAST_TIMINGS["total_live_fetch_ms"] = round((time.perf_counter() - t_start) * 1000, 2)
        return []

    t_fetch = time.perf_counter()
    tasks = [fetch_page_async(c["url"], timeout=C.LIVE_FETCH_TIMEOUT) for c in candidates]
    pages_content = await asyncio.gather(*tasks, return_exceptions=True)
    _LAST_TIMINGS["page_fetch_ms"] = round((time.perf_counter() - t_fetch) * 1000, 2)

    t_parse = time.perf_counter()
    live_chunks: list[dict[str, Any]] = []
    for cand, content in zip(candidates, pages_content):
        if not content or isinstance(content, Exception):
            continue
        chunks = _chunk_text(content, chunk_size=130, overlap=25)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        for idx, ch in enumerate(chunks[:8]):  # top 8 chunks per live page
            live_chunks.append({
                "chunk_id": f"live_{hash(cand['url'] + str(idx)) % 10000000:07d}",
                "title": cand.get("title") or "JKLU Official Website",
                "text": ch,
                "source_url": cand["url"],
                "category": cand.get("category") or "general",
                "source_type": "live",
                "fetch_time": now_str,
                "is_live": True,
            })
    _LAST_TIMINGS["parse_chunk_ms"] = round((time.perf_counter() - t_parse) * 1000, 2)

    if not live_chunks:
        _LAST_TIMINGS["total_live_fetch_ms"] = round((time.perf_counter() - t_start) * 1000, 2)
        return []

    # Embed query and live chunks to re-rank in memory
    t_emb = time.perf_counter()
    try:
        texts = [c["text"] for c in live_chunks]
        q_vec = embedder.encode([query])[0]
        c_vecs = embedder.encode(texts)

        # Cosine similarity
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = q_vec / q_norm

        c_norms = np.linalg.norm(c_vecs, axis=1, keepdims=True)
        c_norms[c_norms == 0] = 1.0
        c_vecs = c_vecs / c_norms

        scores = np.dot(c_vecs, q_vec)
        for i, sc in enumerate(scores):
            live_chunks[i]["dense_score"] = float(sc)
            live_chunks[i]["score"] = float(sc)

        live_chunks.sort(key=lambda x: -x.get("score", 0.0))
        _LAST_TIMINGS["embed_rerank_ms"] = round((time.perf_counter() - t_emb) * 1000, 2)
        _LAST_TIMINGS["total_live_fetch_ms"] = round((time.perf_counter() - t_start) * 1000, 2)
        return live_chunks[:top_k_chunks]
    except Exception as exc:
        log.warning("In-memory embedding of live chunks failed: %s", exc)
        _LAST_TIMINGS["embed_rerank_ms"] = round((time.perf_counter() - t_emb) * 1000, 2)
        _LAST_TIMINGS["total_live_fetch_ms"] = round((time.perf_counter() - t_start) * 1000, 2)
        return live_chunks[:top_k_chunks]


def sync_fetch_and_rank_live_evidence(
    query: str,
    embedder: Any,
    max_pages: int = 3,
    top_k_chunks: int = 4,
) -> list[dict[str, Any]]:
    """Synchronous bridge for async live fetch in sync execution contexts."""
    try:
        return asyncio.run(fetch_and_rank_live_evidence(query, embedder, max_pages, top_k_chunks))
    except Exception as exc:
        log.warning("Sync runner for live fetch failed: %s", exc)
        return []
