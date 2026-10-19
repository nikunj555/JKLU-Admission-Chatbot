"""Shared helpers: logging, text cleaning, JSONL IO, hashing."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
import unicodedata
from pathlib import Path
from typing import Iterable, Iterator

for _stream in (sys.stdout, sys.stderr):          # Windows consoles: never crash on ₹, – or similar
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(message)s"


def get_logger(name: str = "jklu") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT, "%H:%M:%S"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


log = get_logger()

# ------------------------------------------------------------------ text
_WS = re.compile(r"[ \t\u00a0\u2000-\u200b\u202f\u205f\u3000]+")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ufeff\u00ad]")
_LOREM = re.compile(r"lorem ipsum|consectetuer adipiscing|aenean (commodo|massa)", re.I)


def normalize_text(text: str) -> str:
    """Unicode-normalise and strip control characters, keep line structure."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _CTRL.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text


def clean_lines(text: str) -> list[str]:
    out: list[str] = []
    for line in normalize_text(text).split("\n"):
        line = _WS.sub(" ", line).strip()
        if line and not _LOREM.search(line):
            out.append(line)
    return out


def sha1(text: str, n: int = 12) -> str:
    return hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()[:n]


def fingerprint(text: str) -> str:
    """Case/whitespace/punctuation-insensitive hash used for de-duplication."""
    norm = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return hashlib.md5(norm.encode("utf-8", "ignore")).hexdigest()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# ------------------------------------------------------------------ IO
def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    path = Path(path)
    if not path.is_file():
        return rows
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # skip a corrupt line rather than failing the run
    return rows


def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    n = 0
    with open(tmp, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    tmp.replace(path)
    return n


def read_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def safe_filename(name: str, default: str = "document") -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return name[:120] or default


def iter_batches(seq: list, size: int) -> Iterator[list]:
    for i in range(0, len(seq), size):
        yield seq[i:i + size]
