"""Phase 1 - data collection, extraction and cleaning.

JKLU website / PDFs  ->  raw cache  ->  clean documents  ->  chunks.jsonl

Design goals
  * never crash: every network / parsing step is isolated and logged
  * work offline: raw cache + bundled snapshot + data/manual/ are fallbacks
  * polite & fast: bounded, parallel, level-based crawl with a time budget
"""
from __future__ import annotations

import re
import threading
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from . import config as C
from . import sources as S
from .chunking import build_chunks
from .utils import (clean_lines, file_sha256, fingerprint, log, read_json, read_jsonl,
                    safe_filename, sha1, write_json, write_jsonl)

try:  # PyMuPDF >= 1.24 prefers `pymupdf`; older installs expose `fitz`
    import pymupdf as fitz  # type: ignore
except Exception:  # pragma: no cover
    try:
        import fitz  # type: ignore
    except Exception:  # pragma: no cover
        fitz = None

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except Exception:  # pragma: no cover
    requests = None

try:
    from bs4 import BeautifulSoup, Comment, NavigableString, Tag
except Exception:  # pragma: no cover
    BeautifulSoup = None

CRAWL_BUDGET_SEC = int(__import__("os").environ.get("JKLU_CRAWL_BUDGET_SEC", "900"))
PDF_CACHE_DAYS = 30
MAX_PDF_PAGES = 800

NOW = lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")  # noqa: E731


# ==========================================================================
# Networking
# ==========================================================================
_tls = threading.local()
_ssl_warned = False


def _session():
    """One requests.Session per thread (sessions are not guaranteed thread-safe)."""
    s = getattr(_tls, "session", None)
    if s is None:
        s = requests.Session()
        retry = Retry(total=3, connect=3, read=2, backoff_factor=0.8,
                      status_forcelist=(429, 500, 502, 503, 504),
                      allowed_methods=frozenset(["GET", "HEAD"]), raise_on_status=False)
        adapter = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=8)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        s.headers.update({
            "User-Agent": C.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.5",
            "Accept-Language": "en-IN,en;q=0.9",
        })
        _tls.session = s
    return s


class FetchError(Exception):
    pass


def fetch(url: str) -> tuple[bytes, str, str]:
    """Download `url`. Returns (content, kind, final_url) with kind in {'pdf','html'}."""
    global _ssl_warned
    if requests is None:
        raise FetchError("requests is not installed")
    max_bytes = C.MAX_PDF_MB * 1024 * 1024
    last_exc: Exception | None = None
    for verify in (True, False):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                resp = _session().get(url, timeout=(C.CONNECT_TIMEOUT, C.READ_TIMEOUT),
                                      stream=True, allow_redirects=True, verify=verify)
            if resp.status_code != 200:
                resp.close()
                raise FetchError(f"HTTP {resp.status_code}")
            final = S.canonicalize(resp.url) or url
            if not S.is_allowed_host(final) and S.is_allowed_host(url):
                resp.close()
                raise FetchError(f"redirected off-site to {final}")
            chunks, size = [], 0
            for block in resp.iter_content(chunk_size=1 << 16):
                if block:
                    size += len(block)
                    if size > max_bytes:
                        resp.close()
                        raise FetchError(f"larger than {C.MAX_PDF_MB} MB")
                    chunks.append(block)
            content = b"".join(chunks)
            ctype = (resp.headers.get("content-type") or "").lower()
            if content[:5] == b"%PDF-" or "pdf" in ctype:
                return content, "pdf", final
            if "html" in ctype or content.lstrip()[:1] == b"<":
                if len(content) > C.MAX_HTML_MB * 1024 * 1024:
                    raise FetchError("HTML too large")
                return content, "html", final
            raise FetchError(f"unsupported content-type '{ctype}'")
        except requests.exceptions.SSLError as exc:
            last_exc = exc
            if verify and not _ssl_warned:
                _ssl_warned = True
                log.warning("SSL verification failed; retrying without verification (public pages only)")
            continue
        except FetchError:
            raise
        except Exception as exc:  # network errors, timeouts, resets ...
            raise FetchError(f"{type(exc).__name__}: {str(exc)[:120]}") from exc
    raise FetchError(f"SSL error: {str(last_exc)[:120]}")


def is_online(timeout: int = 8) -> bool:
    """Cheap connectivity probe so an offline machine does not wait on dozens of timeouts."""
    if requests is None:
        return False
    for _ in range(2):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                r = requests.get("https://jklu.edu.in", timeout=(timeout, timeout + 7), stream=True,
                                 verify=False, headers={"User-Agent": C.USER_AGENT})
            r.close()
            return r.status_code < 500
        except Exception:
            time.sleep(0.5)
    return False


# ==========================================================================
# Raw cache
# ==========================================================================
class RawCache:
    """url -> raw file on disk, so later runs (and offline runs) reuse downloads."""

    def __init__(self):
        self.lock = threading.Lock()
        self.manifest: dict[str, dict] = read_json(C.MANIFEST_PATH, {}) or {}

    def get(self, url: str) -> tuple[bytes, str, dict] | None:
        ent = self.manifest.get(url)
        if not ent:
            return None
        path = C.ROOT / ent["file"]
        try:
            return path.read_bytes(), ent["kind"], ent
        except Exception:
            return None

    def put(self, url: str, content: bytes, kind: str) -> None:
        folder = C.RAW_PDF_DIR if kind == "pdf" else C.RAW_HTML_DIR
        ext = ".pdf" if kind == "pdf" else ".html"
        base = safe_filename(Path(urlparse(url).path).name or urlparse(url).hostname or "page")
        if not base.lower().endswith(ext):
            base = f"{base}{ext}" if kind == "pdf" or "." not in base else base
        with self.lock:
            existing = self.manifest.get(url)
            if existing:
                name = Path(existing["file"]).name
            else:
                name = base if not any(
                    e["file"].endswith("/" + base) for e in self.manifest.values()) else f"{sha1(url, 6)}_{base}"
            path = folder / name
            try:
                folder.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
                self.manifest[url] = {"file": str(path.relative_to(C.ROOT)).replace("\\", "/"),
                                      "kind": kind, "fetched_at": NOW()}
            except Exception as exc:
                log.warning("cache write failed for %s: %s", url, exc)

    def fresh_pdf(self, url: str) -> bool:
        ent = self.manifest.get(url)
        if not ent or ent.get("kind") != "pdf" or not (C.ROOT / ent["file"]).is_file():
            return False
        try:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(ent["fetched_at"])
            return age.days < PDF_CACHE_DAYS
        except Exception:
            return True

    def save(self) -> None:
        try:
            write_json(C.MANIFEST_PATH, self.manifest)
        except Exception as exc:
            log.warning("could not save manifest: %s", exc)


# ==========================================================================
# HTML extraction
# ==========================================================================
_SKIP_TAGS = {"script", "style", "noscript", "svg", "iframe", "canvas", "form", "button", "select",
              "option", "footer", "template", "head", "picture", "video", "audio"}
# Note: 'nav', 'header', 'aside' are NOT skipped — JKLU uses them for contact info and breadcrumbs.
# We only skip them if they carry aria-label="breadcrumb" or role="navigation" (handled in _walk).
_BLOCK_TAGS = {"p", "div", "section", "article", "main", "li", "ul", "ol", "dl", "dt", "dd", "tr",
               "blockquote", "figure", "figcaption", "address", "pre", "details", "summary",
               "h1", "h2", "h3", "h4", "h5", "h6", "nav", "header", "aside"}
_HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_GENERIC_TITLES = {"jk lakshmipat university", "jklu", "official website"}
_YEAR_RX = re.compile(r"\b(20\d{2})\s*[-–/]\s*(\d{2,4})\b")
# Currency and encoding artifact cleanup
_CURRENCY_RX = re.compile(r"[₹\u20b9]", re.UNICODE)       # Indian Rupee symbol -> INR
_ENCODING_JUNK = re.compile(r"[^\x09\x0a\x0d\x20-\x7e\u00a0-\u024f\u0900-\u097f\u2000-\u206f\u20b9\u2122©®™°–—…''""•]")
_RUPEE_I_RX = re.compile(r"\bI(?=\d{1,3}(?:,\d{2,3})+)")


def _clean_text(text: str) -> str:
    """Normalise currency symbols, fix encoding artifacts, collapse whitespace."""
    text = _CURRENCY_RX.sub("INR ", text)
    text = _RUPEE_I_RX.sub("INR ", text)
    text = _ENCODING_JUNK.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()



def _decode_cfemail(hexstr: str) -> str:
    """Decode Cloudflare's e-mail obfuscation (`[email protected]`)."""
    try:
        key = int(hexstr[:2], 16)
        return "".join(chr(int(hexstr[i:i + 2], 16) ^ key) for i in range(2, len(hexstr), 2))
    except Exception:
        return ""


def _restore_emails(soup) -> None:
    for tag in soup.find_all(attrs={"data-cfemail": True}):
        addr = _decode_cfemail(tag.get("data-cfemail", ""))
        if addr:
            tag.clear()
            tag.append(addr)
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "email-protection#" in href:
            addr = _decode_cfemail(href.split("#", 1)[1])
            if addr and "@" not in a.get_text():
                a.clear()
                a.append(addr)
        elif href.lower().startswith("mailto:"):
            addr = href[7:].split("?", 1)[0].strip()
            if addr and "@" not in a.get_text():
                a.append(f" {addr}")
        elif href.lower().startswith("tel:"):
            num = href[4:].strip()
            if num and num.replace(" ", "") not in a.get_text().replace(" ", ""):
                a.append(f" {num}")


def _table_lines(table) -> list[str]:
    rows = []
    for tr in table.find_all("tr"):
        cells = [_clean_text(re.sub(r"\s+", " ", c.get_text(" ", strip=True))) for c in tr.find_all(["th", "td"])]
        if any(cells):
            rows.append((cells, bool(tr.find("th")) and not tr.find("td")))
    if not rows:
        return []
    header, body = None, rows
    if rows[0][1] or (len(rows) > 1 and len(rows[0][0]) > 1):
        header, body = rows[0][0], rows[1:]
    lines: list[str] = []
    for cells, _ in body:
        cells = [c for c in cells]
        if header and len(cells) == len(header) and len(cells) > 1:
            parts = [f"{h}: {c}" if h else c for h, c in zip(header, cells) if c and c != "-"]
            line = "; ".join(parts)
        else:
            line = " | ".join(c for c in cells if c)
        if line:
            lines.append(line)
    if not body and header:
        lines.append(" | ".join(header))
    return lines


def _walk(node, lines: list[str], buf: list[str], depth: int = 0) -> None:
    def flush(prefix: str = ""):
        text = re.sub(r"\s+", " ", "".join(buf)).strip()
        buf.clear()
        if text:
            cleaned = _clean_text(text)
            if cleaned:
                lines.append(prefix + cleaned)

    for child in node.children:
        if isinstance(child, Comment):
            continue
        if isinstance(child, NavigableString):
            buf.append(str(child))
            continue
        if not isinstance(child, Tag):
            continue
        name = (child.name or "").lower()
        if name in _SKIP_TAGS:
            continue
        if child.get("aria-hidden") == "true" and name not in _HEADINGS:
            continue
        # Skip breadcrumb navs and site navigation (but NOT content navs like contact sections)
        role = (child.get("role") or "").lower()
        aria_label = (child.get("aria-label") or "").lower()
        if name in ("nav", "header") and ("breadcrumb" in aria_label or role == "navigation"):
            continue
        if name == "table":
            flush()
            lines.extend(_table_lines(child))
            continue
        if name == "br":
            flush()
            continue
        if name in _HEADINGS:
            flush()
            _walk(child, lines, buf, depth + 1)
            flush("# ")
        elif name in _BLOCK_TAGS:
            flush()
            _walk(child, lines, buf, depth + 1)
            flush()
        else:
            buf.append(" ")
            _walk(child, lines, buf, depth + 1)
            buf.append(" ")


def extract_html(content: bytes, url: str) -> dict:
    """Return {'title', 'lines', 'links': [(url, anchor)]}."""
    if BeautifulSoup is None:
        raise RuntimeError("beautifulsoup4 is not installed")
    parser = "lxml"
    try:
        soup = BeautifulSoup(content, parser)
    except Exception:
        soup = BeautifulSoup(content, "html.parser")
    _restore_emails(soup)

    # links (collected before nav/footer are dropped so discovery still works)
    links: list[tuple[str, str]] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        absolute = S.canonicalize(urljoin(url, href))
        if absolute:
            links.append((absolute, re.sub(r"\s+", " ", a.get_text(" ", strip=True))[:120]))

    title = ""
    if soup.title and soup.title.string:
        title = re.sub(r"\s+", " ", soup.title.get_text(" ")).strip()
    h1 = soup.find("h1")
    h1_text = re.sub(r"\s+", " ", h1.get_text(" ", strip=True)) if h1 else ""

    root = soup.find("main") or soup.find("article") or soup.body or soup
    lines: list[str] = []
    try:
        _walk(root, lines, [])
    except RecursionError:
        lines = [_clean_text(l) for l in clean_lines(root.get_text("\n")) if _clean_text(l)]
    # a <main> that is nearly empty (JS shells): fall back to whole body
    if sum(len(l.split()) for l in lines) < 40 and root is not soup.body and soup.body is not None:
        alt: list[str] = []
        try:
            _walk(soup.body, alt, [])
            if sum(len(l.split()) for l in alt) > sum(len(l.split()) for l in lines):
                lines = alt
        except RecursionError:
            pass
    return {"title": title, "h1": h1_text, "lines": lines, "links": links}


def _short_title(raw: str, h1: str, fallback: str) -> str:
    cand = (raw or "").split("|")[0].strip(" -–—|")
    if not cand or cand.lower() in _GENERIC_TITLES:
        cand = h1 or fallback
    return cand[:140] or fallback


# ==========================================================================
# PDF extraction
# ==========================================================================
_PRIVATE_USE = re.compile(r"[\ue000-\uf8ff]")
_PAGE_NO = re.compile(r"^(page\s*)?\d{1,4}(\s*(of|/)\s*\d{1,4})?$", re.I)
_NUM_HEADING = re.compile(r"^\d+(\.\d+){0,3}[.)]?\s+[A-Z][^.!?]{2,90}$")


def _looks_like_heading(line: str) -> bool:
    words = line.split()
    if not 1 <= len(words) <= 12 or line.endswith((".", ",", ";", ":")) and len(words) > 4:
        return False
    letters = [c for c in line if c.isalpha()]
    if len(letters) >= 4 and line.upper() == line:
        return True
    return bool(_NUM_HEADING.match(line))


def _extract_pdf_tables(page) -> tuple[list[str], list[tuple[float, float, float, float]]]:
    """Extract structured tables from a PDF page using PyMuPDF find_tables().
    Returns (formatted_lines, list_of_table_bboxes).
    """
    lines: list[str] = []
    bboxes: list[tuple[float, float, float, float]] = []
    if not hasattr(page, "find_tables"):
        return lines, bboxes
    try:
        tabs = page.find_tables()
        if not tabs or not getattr(tabs, "tables", None):
            return lines, bboxes
        for tab in tabs.tables:
            bboxes.append(tab.bbox)
            raw_rows = tab.extract()
            if not raw_rows or len(raw_rows) < 1:
                continue
            rows = []
            for r in raw_rows:
                cells = [_clean_text(str(c or "").replace("\n", " ").strip()) for c in r]
                if any(cells):
                    rows.append(cells)
            if not rows:
                continue

            header = rows[0]
            # Markdown table format
            lines.append(" | ".join(h for h in header))
            lines.append(" | ".join(["---"] * len(header)))
            for row in rows[1:]:
                lines.append(" | ".join(row))

            # Row-keyed representation (for dense & sparse retrieval grounding)
            if len(rows) > 1 and len(header) > 1:
                for row in rows[1:]:
                    if len(row) == len(header):
                        pairs = [f"{h}: {c}" for h, c in zip(header, row) if h and c and c not in ("-", "—", "")]
                        if pairs:
                            lines.append("; ".join(pairs))

                # Special handling for column-oriented / transposed tables (e.g. residence charges)
                if len(header) >= 3 and len(rows) >= 2 and any(k in rows[1][0].lower() for k in ("fee", "charges", "total", "amount", "cost")):
                    col_headers = header[1:]
                    for c_idx, col_name in enumerate(col_headers, start=1):
                        col_pairs = [f"{header[0]}: {col_name}"]
                        for row in rows[1:]:
                            if c_idx < len(row) and row[c_idx] and row[c_idx] not in ("-", "—", ""):
                                col_pairs.append(f"{row[0]}: {row[c_idx]}")
                        lines.append("; ".join(col_pairs))
    except Exception as exc:
        log.debug("PDF table extraction skipped: %s", exc)
    return lines, bboxes


def extract_pdf(content: bytes) -> list[tuple[int, list[str]]]:
    """Return [(page_no, [lines])]. Repeated headers/footers and page numbers are removed."""
    if fitz is None:
        raise RuntimeError("PyMuPDF is not installed")
    doc = fitz.open(stream=content, filetype="pdf")
    try:
        if getattr(doc, "needs_pass", False) and not doc.authenticate(""):
            raise RuntimeError("PDF is password protected")
        pages: list[tuple[int, list[str]]] = []
        for i, page in enumerate(doc):
            if i >= MAX_PDF_PAGES:
                break
            table_lines, table_bboxes = _extract_pdf_tables(page)
            try:
                try:
                    blocks = page.get_text("blocks", sort=True)
                except TypeError:
                    blocks = page.get_text("blocks")
            except Exception:
                continue
            lines: list[str] = []
            for b in blocks:
                if len(b) < 7 or b[6] != 0:      # skip image blocks
                    continue
                bx0, by0, bx1, by1 = b[0], b[1], b[2], b[3]
                cx, cy = (bx0 + bx1) / 2.0, (by0 + by1) / 2.0
                if any(tx0 <= cx <= tx1 and ty0 <= cy <= ty1 for tx0, ty0, tx1, ty1 in table_bboxes):
                    continue
                txt = _PRIVATE_USE.sub("• ", b[4] or "")
                txt = _clean_text(txt)              # normalise ₹ -> INR, fix encoding artifacts
                txt = re.sub(r"-\n(?=[a-z])", "", txt)         # de-hyphenate
                txt = re.sub(r"\s*\n\s*", " ", txt)
                for line in clean_lines(txt):
                    lines.append(line)
            lines.extend(table_lines)
            if lines:
                pages.append((i + 1, lines))
    finally:
        doc.close()
    return _strip_page_furniture(pages)


def _strip_page_furniture(pages: list[tuple[int, list[str]]]) -> list[tuple[int, list[str]]]:
    """Remove running headers/footers (repeated near page edges) and bare page numbers."""
    if not pages:
        return pages
    EDGE = 3

    def key(l: str) -> str:
        return re.sub(r"\d+", "#", l.lower())

    def edge_idx(n_lines: int) -> set[int]:
        return set(range(min(EDGE, n_lines))) | set(range(max(0, n_lines - EDGE), n_lines))

    freq: dict[str, int] = {}
    for _, lines in pages:
        keys = {key(lines[i]) for i in edge_idx(len(lines)) if len(lines[i].split()) <= 14}
        for k in keys:
            freq[k] = freq.get(k, 0) + 1
    n = len(pages)
    repeated = {k for k, v in freq.items() if n >= 4 and v >= max(3, int(0.4 * n))}
    out = []
    for no, lines in pages:
        edges = edge_idx(len(lines))
        kept = []
        for i, l in enumerate(lines):
            if _PAGE_NO.match(l) or (i in edges and key(l) in repeated):
                continue
            kept.append("# " + l if _looks_like_heading(l) else l)
        if kept:
            out.append((no, kept))
    return out


# ==========================================================================
# Document building
# ==========================================================================
_ANY_YEAR = re.compile(r"\b(20[0-3]\d)\b")


def _academic_year(title: str, url: str, first_text: str) -> str | None:
    """'2026-27' style academic year if present, else the newest plausible year in the title/lead text."""
    for t in (title, url, first_text):
        for m in _YEAR_RX.finditer(t or ""):
            a, b = int(m.group(1)), int(m.group(2)[-2:])
            if 1 <= (b - a) % 100 <= 4:                 # real academic year / batch, not a date like 2021/06
                return f"{a}-{b:02d}"
    max_year = datetime.now(timezone.utc).year + 1
    years = [int(y) for t in (title, first_text) for y in _ANY_YEAR.findall(t or "") if int(y) <= max_year]
    return str(max(years)) if years else None


def make_doc(url: str, category: str, title: str, source_type: str,
             pages: list[tuple[int | None, list[str]]], priority: int = 2,
             fetched_at: str | None = None, extra: dict | None = None) -> dict | None:
    pages = [(no, [l for l in lines if l.strip()]) for no, lines in pages]
    pages = [(no, lines) for no, lines in pages if lines]
    words = sum(len(l.split()) for _, lines in pages for l in lines)
    if words < C.MIN_DOC_WORDS:
        return None
    first_text = " ".join(l for _, lines in pages[:1] for l in lines[:12])[:700]
    doc = {
        "doc_id": sha1(url, 10),
        "url": url,
        "title": title,
        "category": category,
        "source_type": source_type,
        "priority": priority,
        "academic_year": _academic_year(title, url, first_text),
        "fetched_at": fetched_at or NOW(),
        "n_words": words,
        "pages": [[no, "\n".join(lines)] for no, lines in pages],
    }
    if extra:
        doc.update(extra)
    return doc


def _doc_from_raw(url: str, kind: str, content: bytes, seed: S.Seed | None, category: str,
                  fetched_at: str | None = None) -> tuple[dict | None, dict]:
    """Parse raw bytes into a document. Returns (doc | None, info) and never raises."""
    info: dict = {"links": []}
    try:
        if kind == "pdf":
            pages = extract_pdf(content)
            if not pages:
                info["note"] = "no extractable text (scanned/image PDF?)"
                return None, info
            title = (seed.title if seed and seed.title else "") or S.title_from_url(url)
            doc = make_doc(url, category, title, "pdf", pages, seed.priority if seed else 1, fetched_at)
            return doc, info
        res = extract_html(content, url)
        info["links"] = res["links"]
        fallback = seed.title if seed and seed.title else S.title_from_url(url)
        title = (seed.title if seed and seed.title else _short_title(res["title"], res["h1"], fallback))
        doc = make_doc(url, category, title, "html", [(None, res["lines"])],
                       seed.priority if seed else 1, fetched_at)
        if doc is None:
            info["note"] = "no usable text (page is likely rendered by JavaScript)"
        return doc, info
    except Exception as exc:
        info["note"] = f"parse error: {type(exc).__name__}: {str(exc)[:100]}"
        return None, info


# ==========================================================================
# Boilerplate removal across the whole corpus (menus, breadcrumbs, CTAs)
# ==========================================================================
_CTA = re.compile(r"^(read more|view|apply now|call now|enquire now|know more|learn more|click here|"
                  r"menu|home|also explore|download|submit|share|follow us|back to top)$", re.I)


def remove_boilerplate(docs: list[dict]) -> int:
    """Drop short lines that repeat across many HTML pages (site chrome)."""
    html_docs = [d for d in docs if d["source_type"] == "html"]
    if len(html_docs) < 4:
        return 0

    def section(d):
        parts = [p for p in urlparse(d["url"]).path.split("/") if p]
        return (urlparse(d["url"]).hostname or "", parts[0] if parts else "")

    per_doc: list[set[str]] = []
    for d in html_docs:
        lines = {l.lower() for _, t in d["pages"] for l in t.split("\n") if len(l.split()) <= 30}
        per_doc.append(lines)
    global_cnt: dict[str, int] = {}
    group_cnt: dict[tuple, dict[str, int]] = {}
    group_size: dict[tuple, int] = {}
    for d, lines in zip(html_docs, per_doc):
        g = section(d)
        group_size[g] = group_size.get(g, 0) + 1
        gc = group_cnt.setdefault(g, {})
        for l in lines:
            global_cnt[l] = global_cnt.get(l, 0) + 1
            gc[l] = gc.get(l, 0) + 1
    n = len(html_docs)
    removed = 0
    for d in html_docs:
        g = section(d)
        new_pages = []
        for no, text in d["pages"]:
            kept = []
            for l in text.split("\n"):
                key = l.lower()
                body = key[2:] if key.startswith("# ") else key
                cnt_global = max(global_cnt.get(key, 0), global_cnt.get(body, 0))
                cnt_group = max(group_cnt[g].get(key, 0), group_cnt[g].get(body, 0))
                is_heading = l.startswith("# ")
                # Never remove section headings unless they are bare CTAs (like # Apply Now)
                if is_heading and not _CTA.match(body):
                    kept.append(l)
                    continue
                # Never remove important office names or lines from contact documents
                if body in {"admissions", "registrar", "placements", "human resources", "media", "hostel", "contact us"}:
                    kept.append(l)
                    continue
                is_chrome = (
                    (n >= 6 and cnt_global >= max(4, 0.3 * n)) or
                    (group_size[g] >= 4 and cnt_group >= max(3, 0.6 * group_size[g]))
                )
                if (is_chrome and len(l.split()) <= 30) or _CTA.match(body):
                    removed += 1
                    continue
                kept.append(l)
            if kept:
                new_pages.append([no, "\n".join(kept)])
        d["pages"] = new_pages
        d["n_words"] = sum(len(t.split()) for _, t in new_pages)
    return removed


# ==========================================================================
# Crawl orchestration
# ==========================================================================
def _seed_index() -> dict[str, S.Seed]:
    idx: dict[str, S.Seed] = {}
    for s in S.SEEDS:
        for u in s.candidates:
            idx[S.canonicalize(u) or u] = s
    return idx


def _snapshot_docs() -> dict[str, dict]:
    return {d["url"]: d for d in read_jsonl(C.SNAPSHOT_DOCS_PATH) if d.get("url")}


def _extract_docx(data: bytes) -> list[str]:
    """Extract paragraphs and table text from a .docx file using built-in zipfile & xml."""
    import io
    import xml.etree.ElementTree as ET
    import zipfile
    lines = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            xml_content = z.read("word/document.xml")
        tree = ET.fromstring(xml_content)
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        for p in tree.iter(f"{ns}p"):
            texts = [node.text for node in p.iter(f"{ns}t") if node.text]
            if texts:
                line = "".join(texts).strip()
                if line:
                    lines.append(line)
    except Exception as exc:
        log.warning("docx extraction failed: %s", exc)
    return lines


def _extract_csv(path: Path) -> list[str]:
    """Format CSV rows into readable key-value sentences."""
    import csv
    lines = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            reader = csv.reader(fh)
            header = None
            for row in reader:
                if not row or not any(row):
                    continue
                if header is None:
                    header = [h.strip() for h in row]
                    lines.append("Columns: " + ", ".join(header))
                else:
                    pairs = [f"{h}: {val.strip()}" for h, val in zip(header, row) if val.strip()]
                    lines.append("; ".join(pairs) if pairs else " | ".join(row))
    except Exception as exc:
        log.warning("csv extraction failed: %s", exc)
    return lines


def _extract_json(path: Path) -> list[str]:
    """Format JSON content into readable text."""
    import json
    lines = []
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    lines.append("; ".join(f"{k}: {v}" for k, v in item.items() if v))
                else:
                    lines.append(str(item))
        elif isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, (list, dict)):
                    lines.append(f"# {k}")
                    if isinstance(v, list):
                        for el in v:
                            lines.append(str(el))
                    else:
                        for sk, sv in v.items():
                            lines.append(f"{sk}: {sv}")
                else:
                    lines.append(f"{k}: {v}")
    except Exception as exc:
        log.warning("json extraction failed: %s", exc)
    return lines


def _manual_docs() -> list[dict]:
    """Documents dropped into data/manual/ and external directories like campus/."""
    import shutil
    docs: list[dict] = []

    dirs_to_scan: list[tuple[Path, str]] = []
    if C.MANUAL_DIR.is_dir():
        dirs_to_scan.append((C.MANUAL_DIR, "manual"))

    for extra_dir in getattr(C, "EXTRA_DATA_DIRS", []):
        if extra_dir.is_dir():
            dirs_to_scan.append((extra_dir, extra_dir.name.lower()))
            # Auto-sync files into data/manual/<folder_name> so they remain in workspace
            target_manual = C.MANUAL_DIR / extra_dir.name.lower()
            try:
                target_manual.mkdir(parents=True, exist_ok=True)
                for f in extra_dir.rglob("*"):
                    if f.is_file():
                        dest = target_manual / f.relative_to(extra_dir)
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        if not dest.is_file() or dest.stat().st_mtime < f.stat().st_mtime:
                            shutil.copy2(f, dest)
            except Exception as exc:
                log.warning("Could not sync extra dir %s to data/manual: %s", extra_dir, exc)

    seen_paths = set()
    for root, scheme in dirs_to_scan:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            ext = path.suffix.lower()
            if ext not in (".pdf", ".txt", ".md", ".html", ".htm", ".docx", ".csv", ".json"):
                continue
            if path.name.lower().startswith("readme") and ext in (".txt", ".md"):
                continue
            norm_key = path.resolve()
            if norm_key in seen_paths:
                continue
            seen_paths.add(norm_key)

            rel = path.relative_to(root)
            folder = rel.parts[0].lower() if len(rel.parts) > 1 else ""
            category = folder if folder in C.CATEGORIES else S.classify(path.name, fallback="general")
            url = f"{scheme}:{rel.as_posix()}"
            title = re.sub(r"[-_]+", " ", path.stem).strip().title()
            try:
                doc = None
                if ext == ".pdf":
                    doc, _ = _doc_from_raw(url, "pdf", path.read_bytes(), None, category)
                    if doc:
                        doc["title"], doc["priority"] = title, 3
                elif ext in (".html", ".htm"):
                    doc, _ = _doc_from_raw(url, "html", path.read_bytes(), None, category)
                    if doc:
                        doc["title"], doc["priority"] = title, 3
                elif ext == ".docx":
                    lines = _extract_docx(path.read_bytes())
                    lines = clean_lines("\n".join(lines))
                    lines = ["# " + l[1:].strip() if l.startswith("#") else l for l in lines]
                    doc = make_doc(url, category, title, "docx", [(None, lines)], 3)
                elif ext == ".csv":
                    lines = _extract_csv(path)
                    doc = make_doc(url, category, title, "csv", [(None, lines)], 3)
                elif ext == ".json":
                    lines = _extract_json(path)
                    doc = make_doc(url, category, title, "json", [(None, lines)], 3)
                else:  # .txt, .md
                    lines = clean_lines(path.read_text(encoding="utf-8", errors="ignore"))
                    lines = ["# " + l[1:].strip() if l.startswith("#") else l for l in lines]
                    doc = make_doc(url, category, title, "text", [(None, lines)], 3)
                if doc:
                    docs.append(doc)
            except Exception as exc:
                log.warning("manual document %s skipped: %s", rel, exc)
    return docs


def _fetch_one(task: dict, cache: RawCache, refresh: bool) -> dict:
    """Fetch (or reuse cache for) one URL and parse it. Always returns a result dict."""
    url, seed = task["url"], task.get("seed")
    res = {"task": task, "doc": None, "links": [], "status": "error", "note": "", "from": "network"}
    try:
        use_cache = (not refresh) and cache.fresh_pdf(url)
        if use_cache:
            content, kind, ent = cache.get(url)  # type: ignore[misc]
            res["from"] = "cache"
            fetched_at, final = ent.get("fetched_at"), url
        else:
            time.sleep(C.CRAWL_DELAY)
            content, kind, final = fetch(url)
            cache.put(url, content, kind)
            fetched_at = NOW()
        doc, info = _doc_from_raw(url, kind, content, seed, task["category"], fetched_at)
        res["links"] = info.get("links", [])
        res["note"] = info.get("note", "")
        res["doc"] = doc
        res["status"] = "ok" if doc else "empty"
        res["content_type"] = kind
    except FetchError as exc:
        res["note"] = str(exc)
        cached = cache.get(url)           # network failed: fall back to older raw copy
        if cached:
            content, kind, ent = cached
            doc, info = _doc_from_raw(url, kind, content, seed, task["category"], ent.get("fetched_at"))
            if doc:
                res.update(doc=doc, links=info.get("links", []), status="ok", **{"from": "cache"})
                res["note"] = f"network failed ({exc}); used cached copy"
    except Exception as exc:  # absolutely never propagate
        res["note"] = f"{type(exc).__name__}: {str(exc)[:120]}"
    return res


def crawl(cache: RawCache, refresh: bool) -> tuple[list[dict], list[dict], dict[str, list[str]]]:
    """Level-based, parallel, bounded crawl. Returns (docs, source_log, links_by_category)."""
    started = time.time()
    seen: set[str] = set()
    docs: list[dict] = []
    log_rows: list[dict] = []
    links_by_cat: dict[str, list[str]] = {c: [] for c in C.CATEGORIES}
    fetched_count = 0
    seed_ok_cat: dict[str, bool] = {}

    # ---- level 0: curated seeds. Candidate URLs are tried in order, first success wins.
    def run_seed(seed: S.Seed) -> dict | None:
        last = None
        for cand in seed.candidates:
            url = S.canonicalize(cand) or cand
            r = _fetch_one({"url": url, "category": seed.category, "seed": seed, "depth": 0}, cache, refresh)
            r["seed"] = seed
            last = r
            log_rows.append(_log_row(r))
            if r["doc"]:
                return r
        return last

    level_results: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, C.CRAWL_WORKERS)) as pool:
        futs = [pool.submit(run_seed, s) for s in S.SEEDS]
        for f in as_completed(futs):
            try:
                r = f.result()
            except Exception as exc:  # pragma: no cover
                log.warning("seed crashed: %s", exc)
                continue
            if r:
                level_results.append(r)
    for s in S.SEEDS:
        for c in s.candidates:
            seen.add(S.canonicalize(c) or c)

    frontier: list[dict] = []
    for r in level_results:                      # record which categories have a curated seed document
        if r["doc"]:
            seed_ok_cat[r["doc"]["category"]] = True
    for r in sorted(level_results, key=lambda x: x["task"]["url"]):
        fetched_count += 1
        _accept(r, docs, links_by_cat, frontier, seen, 0, seed_ok_cat)
    log.info("seeds: %d/%d documents collected", len(docs), len(S.SEEDS))

    # ---- deeper levels: discovered links
    depth = 1
    while frontier and depth <= C.MAX_DEPTH and fetched_count < C.MAX_PAGES \
            and time.time() - started < CRAWL_BUDGET_SEC:
        batch = frontier[: C.MAX_PAGES - fetched_count]
        frontier = []
        results: list[dict] = []
        with ThreadPoolExecutor(max_workers=max(1, C.CRAWL_WORKERS)) as pool:
            futs = [pool.submit(_fetch_one, t, cache, refresh) for t in batch]
            for f in as_completed(futs):
                try:
                    r = f.result()
                except Exception:  # pragma: no cover
                    continue
                log_rows.append(_log_row(r))
                results.append(r)
        for r in sorted(results, key=lambda x: x["task"]["url"]):
            fetched_count += 1
            _accept(r, docs, links_by_cat, frontier, seen, depth, seed_ok_cat)
        log.info("depth %d: %d fetched, %d queued", depth, len(batch), len(frontier))
        depth += 1
    return docs, log_rows, links_by_cat


def _accept(r: dict, docs: list[dict], links_by_cat: dict, frontier: list[dict],
            seen: set[str], depth: int, seed_ok_cat: dict) -> None:
    task = r["task"]
    doc = r["doc"]
    if r["status"] == "ok" and doc:
        docs.append(doc)
        links_by_cat.setdefault(doc["category"], []).append(doc["url"])
        if task.get("seed") is not None or depth == 0:
            seed_ok_cat[doc["category"]] = True
    elif r["status"] != "ok":
        log.warning("  skipped %s (%s)", task["url"], r["note"] or r["status"])
    if depth >= C.MAX_DEPTH or doc is None or doc["source_type"] != "html":
        return
    for link, anchor in r["links"]:
        if link in seen or not S.should_follow(link):
            continue
        cat = S.classify(link, anchor, fallback=doc["category"])
        # the yearly hostel policy is a seeded curated document; never mix in older versions
        if cat == "hostel" and S.is_pdf_url(link) and seed_ok_cat.get("hostel"):
            continue
        seen.add(link)
        frontier.append({"url": link, "category": cat, "seed": None, "depth": depth + 1})


def _log_row(r: dict) -> dict:
    t = r["task"]
    row = {"url": t["url"], "category": t["category"], "status": r["status"],
           "source": r.get("from"), "fetched_at": NOW()}
    if r.get("note"):
        row["note"] = r["note"]
    return row


def offline_docs(cache: RawCache) -> list[dict]:
    """Rebuild the document set from the raw cache + bundled snapshot (no network)."""
    seeds = _seed_index()
    docs: list[dict] = []
    done: set[str] = set()
    for url, ent in sorted(cache.manifest.items()):
        got = cache.get(url)
        if not got:
            continue
        content, kind, ent = got
        seed = seeds.get(url)
        cat = seed.category if seed else S.classify(url, fallback="academics")
        if not seed and not S.should_follow(url):
            continue
        doc, _ = _doc_from_raw(url, kind, content, seed, cat, ent.get("fetched_at"))
        if doc:
            docs.append(doc)
            done.add(url)
    for url, d in _snapshot_docs().items():
        if url in done:
            continue
        seed = seeds.get(S.canonicalize(url) or url)
        if not seed and not S.should_follow(url):
            continue
        d = dict(d)
        d["category"] = seed.category if seed else S.classify(url, fallback=d.get("category", "general"))
        if seed:
            d["title"], d["priority"] = seed.title or d["title"], seed.priority
        docs.append(d)
        done.add(url)
    return docs


def fill_missing_from_fallbacks(docs: list[dict], cache: RawCache) -> int:
    """Online run, but some seeds failed: back-fill them from the snapshot."""
    have = {d["url"] for d in docs}
    seeds = _seed_index()
    snap = _snapshot_docs()
    added = 0
    for seed in S.SEEDS:
        if any((S.canonicalize(c) or c) in have for c in seed.candidates):
            continue
        for cand in seed.candidates:
            url = S.canonicalize(cand) or cand
            d = snap.get(url)
            if d:
                d = dict(d)
                d.update(category=seed.category, title=seed.title or d["title"], priority=seed.priority)
                docs.append(d)
                added += 1
                log.info("  back-filled from snapshot: %s", url)
                break
    return added


def dedupe_documents(docs: list[dict]) -> list[dict]:
    """Drop exact duplicate documents (same URL or same text), keeping the higher priority."""
    docs = sorted(docs, key=lambda d: (-int(d.get("priority", 1)), d["url"]))
    seen_url, seen_text, out = set(), set(), []
    for d in docs:
        text = " ".join(t for _, t in d["pages"])
        fp = fingerprint(text)
        if d["url"] in seen_url or fp in seen_text:
            continue
        seen_url.add(d["url"])
        seen_text.add(fp)
        out.append(d)
    return out


# ==========================================================================
# Public entry point
# ==========================================================================
def run_ingestion(offline: bool = False, refresh: bool = False) -> dict:
    """Run Phase 1 end-to-end and write documents/chunks/sources files. Never raises."""
    t0 = time.time()
    for d in (C.RAW_PDF_DIR, C.RAW_HTML_DIR, C.PROCESSED_DIR, C.MANUAL_DIR):
        d.mkdir(parents=True, exist_ok=True)
    cache = RawCache()
    log_rows: list[dict] = []
    links_by_cat: dict[str, list[str]] = {c: [] for c in C.CATEGORIES}
    docs: list[dict] = []
    mode = "offline"

    try:
        online = (not offline) and is_online()
        if not offline and not online:
            log.warning("No connection to jklu.edu.in - using cached/bundled data (offline mode)")
        if online:
            mode = "online"
            log.info("Crawling the official JKLU website (parallel, bounded) ...")
            docs, log_rows, links_by_cat = crawl(cache, refresh)
            cache.save()
            fill_missing_from_fallbacks(docs, cache)
        if not docs:
            mode = "offline"
            docs = offline_docs(cache)
            log.info("Offline: %d documents rebuilt from cache/snapshot", len(docs))
    except Exception as exc:  # last line of defence
        log.error("crawl failed (%s: %s) - falling back to cache", type(exc).__name__, exc)
        docs = docs or offline_docs(cache)

    manual = _manual_docs()
    if manual:
        log.info("Manual documents added from data/manual: %d", len(manual))
    docs.extend(manual)

    docs = dedupe_documents(docs)
    removed = remove_boilerplate(docs)
    docs = [d for d in docs if d["n_words"] >= C.MIN_DOC_WORDS]
    for d in docs:
        if not d.get("academic_year"):
            lead = " ".join(t for _, t in d["pages"][:1])[:700]
            d["academic_year"] = _academic_year(d["title"], d["url"], lead)
    log.info("Documents: %d | boilerplate lines removed: %d", len(docs), removed)

    chunks = build_chunks(docs)
    write_jsonl(C.DOCUMENTS_PATH, docs)
    write_jsonl(C.CHUNKS_PATH, chunks)
    write_json(C.SOURCES_PATH, log_rows)
    if not any(links_by_cat.values()):
        for d in docs:
            links_by_cat.setdefault(d["category"], []).append(d["url"])
    write_json(C.LINKS_PATH, links_by_cat)

    per_cat: dict[str, int] = {}
    for c in chunks:
        per_cat[c["category"]] = per_cat.get(c["category"], 0) + 1
    summary = {"mode": mode, "documents": len(docs), "chunks": len(chunks),
               "chunks_per_category": dict(sorted(per_cat.items())),
               "seconds": round(time.time() - t0, 1)}
    missing = [c for c in C.CATEGORIES if c not in per_cat]
    if missing:
        log.warning("Categories with no data: %s", ", ".join(missing))
    log.info("Phase 1 done: %d documents -> %d chunks in %.1fs", len(docs), len(chunks), summary["seconds"])
    return summary


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="JKLU Phase 1: collect, clean and chunk")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--refresh", action="store_true", help="re-download PDFs even if cached")
    a = ap.parse_args()
    print(run_ingestion(offline=a.offline, refresh=a.refresh))
