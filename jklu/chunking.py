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
_ROMAN_SEM = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8}
_SEM_HDR_RX = re.compile(r"(?:^|\|\s*)Semester\s*[-:]?\s*(VIII|VII|VI|IV|III|II|I|V|[1-8])\b", re.I)
_COURSE_ROW_PIPE_RX = re.compile(
    r"^\s*(?:\d+|[A-Z])\s*\|\s*([A-Z]{2,4}\d{3,4}|-)\s*\|\s*([^|]+?)\s*\|\s*([0-9]+-[0-9]+-[0-9]+|\d+)\b"
)
_BBA_HTML_ROW_RX = re.compile(
    r"Type of Subject:\s*([^;]+);\s*Name of Subject:\s*([^;]+);\s*Credits:\s*(\d+(?:\.\d+)?)", re.I
)
_BDES_HTML_ROW_RX = re.compile(
    r"^Course Title:\s*([^;]+);\s*Credits:\s*(\d+(?:\.\d+)?)", re.I
)
_TOTAL_ROW_RX = re.compile(r"^(?:Total\s*\|\s*\d+|Course Title:\s*Total;\s*Credits:\s*\d+)", re.I)


def _infer_curriculum_meta(doc: dict) -> tuple[bool, str | None, str | None, str | None]:
    title = (doc.get("title") or "").strip()
    url = (doc.get("url") or "").lower()
    tl = title.lower()
    if "b.tech cse (ai)" in tl or "cse_ai" in url:
        return True, "B.Tech", "CSE (AI)", "2023-27"
    if "b.tech cse" in tl or "btech-cse" in url:
        return True, "B.Tech", "CSE", "2023-27"
    if "bba fintech" in tl or "administration-fintech" in url:
        return True, "BBA", "BBA FinTech", "current"
    if "bba kpmg" in tl or "administration-kpmg" in url:
        return True, "BBA", "BBA KPMG", "current"
    if "handbook-bba-2021-24" in url or "bba curriculum handbook 2021-24" in tl:
        return True, "BBA", "BBA", "2021-24"
    if "bba curriculum" in tl or url.endswith("/programme/bachelor-of-business-administration"):
        return True, "BBA", "BBA", "current"
    if "b.des product design curriculum" in tl or "bdes-product-design" in url:
        return True, "B.Des", "B.Des Product Design", "current"
    if "b.des interaction design syllabus handbook 2021-25" in tl or "b.des-interaction" in url:
        return True, "B.Des", "B.Des Interaction Design", "2021-25"
    if "b.des interaction design curriculum" in tl or "bdes-interaction-design" in url:
        return True, "B.Des", "B.Des Interaction Design", "current"
    if "b.des interdisciplinary design syllabus handbook 2021-25" in tl or "b.des-interdisciplinary" in url:
        return True, "B.Des", "B.Des Interdisciplinary Design", "2021-25"
    if "b.des interdisciplinary design curriculum" in tl or "bdes-interdisciplinary-design" in url:
        return True, "B.Des", "B.Des Interdisciplinary Design", "current"
    if "b.des integrated communication design curriculum" in tl or "bdes-integrated-communication-design" in url:
        return True, "B.Des", "B.Des Integrated Communication Design", "current"
    if "phd coursework" in tl or "phd-coursework" in url:
        return True, "PhD", "PhD", "2024-25"
    return False, None, None, None


def _parse_sem_number(text: str) -> int | None:
    m = _SEM_HDR_RX.search(text or "")
    if not m:
        return None
    val = m.group(1).strip().lower()
    if val.isdigit():
        n = int(val)
        return n if 1 <= n <= 8 else None
    return _ROMAN_SEM.get(val)


def _extract_courses_from_text(text: str) -> list[dict]:
    courses: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        m = _COURSE_ROW_PIPE_RX.match(line)
        if m:
            code, title, credits = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
            if title and title.lower() not in ("course name", "course title"):
                key = (code, title.lower())
                if key not in seen:
                    seen.add(key)
                    courses.append({"code": code, "title": title, "credits": credits})
            continue
        mb = _BBA_HTML_ROW_RX.search(line)
        if mb:
            ctype, title, credits = mb.group(1).strip(), mb.group(2).strip(), mb.group(3).strip()
            key = (ctype, title.lower())
            if key not in seen:
                seen.add(key)
                courses.append({"code": ctype, "title": title, "credits": credits})
            continue
        md = _BDES_HTML_ROW_RX.match(line)
        if md:
            title, credits = md.group(1).strip(), md.group(2).strip()
            if title.lower() != "total":
                key = ("-", title.lower())
                if key not in seen:
                    seen.add(key)
                    courses.append({"code": "-", "title": title, "credits": credits})
    return courses


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
    is_curr, prog, dept, batch = _infer_curriculum_meta(doc)
    is_html_curr = is_curr and doc.get("source_type") == "html"
    target, overlap = C.CHUNK_WORDS, C.CHUNK_OVERLAP_WORDS
    chunks: list[list[tuple[str, int | None, str]]] = []
    cur: list[tuple[str, int | None, str]] = []
    cur_words = 0
    has_new = False            # does `cur` hold units not yet emitted in a chunk?
    for u in units:
        w = len(u[0].split())
        # Never carry previous-semester rows into a new semester chunk
        if is_curr and cur and _parse_sem_number(u[0]) is not None:
            chunks.append(cur)
            cur, cur_words = [], 0
            has_new = False
        elif is_html_curr and cur and _TOTAL_ROW_RX.match(u[0]):
            cur.append(u)
            chunks.append(cur)
            cur, cur_words = [], 0
            has_new = False
            continue
        elif cur and cur_words + w > target and not (is_html_curr and cur and (_BBA_HTML_ROW_RX.search(u[0]) or _BDES_HTML_ROW_RX.match(u[0]))):
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
    active_sem: int | None = None
    html_sem = 1
    for i, group in enumerate(chunks):
        text = "\n".join(t for t, _, _ in group).strip()
        if len(text.split()) < min(C.MIN_CHUNK_WORDS, 6) and n_chunks > 1:
            continue
        pages = [p for _, p, _ in group if p is not None]
        sec = next((h for _, _, h in group if h), "")
        courses = _extract_courses_from_text(text) if is_curr else []
        if is_curr:
            sem_here = _parse_sem_number(text)
            if sem_here is not None:
                active_sem = sem_here
            elif is_html_curr and courses and html_sem <= 8:
                active_sem = html_sem
                html_sem += 1
        chunk_row = {
            "chunk_id": f"{doc['doc_id']}-{i:04d}",
            "doc_id": doc["doc_id"],
            "chunk_index": i,
            "total_chunks": n_chunks,
            "prev_chunk_id": f"{doc['doc_id']}-{i-1:04d}" if i > 0 else None,
            "next_chunk_id": f"{doc['doc_id']}-{i+1:04d}" if i + 1 < n_chunks else None,
            "text": text,
            "category": "curriculum" if is_curr else doc["category"],
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
        }
        if is_curr:
            chunk_row["programme"] = prog
            chunk_row["department"] = dept
            chunk_row["batch"] = batch
            chunk_row["semester"] = active_sem
            chunk_row["year"] = ((active_sem + 1) // 2) if active_sem else None
            if courses:
                chunk_row["courses"] = courses
                chunk_row["course_codes"] = [c["code"] for c in courses if c["code"] != "-"]
        out.append(chunk_row)
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
