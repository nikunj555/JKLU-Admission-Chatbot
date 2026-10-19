"""Central configuration. Every value can be overridden with an environment
variable or a `.env` file in the project root (see `.env.example`)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Tiny .env loader (no external dependency). Supports UTF-8, UTF-8 BOM, UTF-16, Latin-1. Existing env vars win."""
    try:
        if not path.is_file():
            return
        raw_bytes = path.read_bytes()
        text = None
        for enc in ("utf-8-sig", "utf-8", "utf-16", "utf-16-le", "latin-1"):
            try:
                decoded = raw_bytes.decode(enc)
                if "=" in decoded:
                    text = decoded
                    break
            except (UnicodeDecodeError, ValueError):
                continue
        if text is None:
            text = raw_bytes.decode("utf-8", errors="ignore")
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key and val and key not in os.environ:
                os.environ[key] = val
    except Exception:
        pass


_load_dotenv(ROOT / ".env")

# Hugging Face: fail fast instead of hanging when offline.
os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "10")
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# ----------------------------------------------------------------- paths
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
RAW_PDF_DIR = RAW_DIR / "pdfs"
RAW_HTML_DIR = RAW_DIR / "html"
PROCESSED_DIR = DATA_DIR / "processed"
SNAPSHOT_DIR = DATA_DIR / "snapshot"
MANUAL_DIR = DATA_DIR / "manual"
TEST_DIR = DATA_DIR / "test"

# External extra data directories (scanned in addition to data/manual)
_extra_raw = os.environ.get("JKLU_EXTRA_DATA_DIRS", r"c:\Users\Nikunj katta\Downloads\campus")
EXTRA_DATA_DIRS = [Path(p.strip()) for p in _extra_raw.split(";") if p.strip()]

MANIFEST_PATH = RAW_DIR / "manifest.json"           # url -> cached raw file
DOCUMENTS_PATH = PROCESSED_DIR / "documents.jsonl"   # cleaned full documents
CHUNKS_PATH = PROCESSED_DIR / "chunks.jsonl"         # chunks (+ metadata)
SOURCES_PATH = PROCESSED_DIR / "sources.json"        # fetch log
LINKS_PATH = PROCESSED_DIR / "links_by_category.json"
SNAPSHOT_DOCS_PATH = SNAPSHOT_DIR / "documents.jsonl"  # bundled offline fallback

VECTOR_DIR = ROOT / "vector_store"
FAISS_PATH = VECTOR_DIR / "jklu.faiss"
METADATA_PATH = VECTOR_DIR / "metadata.json"
INDEX_INFO_PATH = VECTOR_DIR / "index_info.json"

RESULTS_DIR = ROOT / "results"
TEST_QUESTIONS_PATH = TEST_DIR / "test_questions.csv"

# ------------------------------------------------------------ categories
CATEGORIES = [
    "admission", "academics", "hostel", "fees", "examination",
    "scholarships", "contact", "notices", "faculty", "general",
]

# ------------------------------------------------------------- crawling
USER_AGENT = os.environ.get(
    "JKLU_USER_AGENT",
    "Mozilla/5.0 (compatible; JKLU-Info-Agent/2.0; educational project)",
)
CONNECT_TIMEOUT = _env_int("JKLU_CONNECT_TIMEOUT", 8)
READ_TIMEOUT = _env_int("JKLU_READ_TIMEOUT", 40)
CRAWL_WORKERS = _env_int("JKLU_CRAWL_WORKERS", 4)
CRAWL_DELAY = _env_float("JKLU_CRAWL_DELAY", 0.25)
MAX_PAGES = _env_int("JKLU_MAX_PAGES", 120)          # html + pdf fetches
MAX_DEPTH = _env_int("JKLU_MAX_DEPTH", 2)
MAX_PDF_MB = _env_int("JKLU_MAX_PDF_MB", 60)
MAX_HTML_MB = 8
MIN_DOC_WORDS = 15            # ignore pages with less text than this

# -------------------------------------------------------------- chunking
CHUNK_WORDS = _env_int("JKLU_CHUNK_WORDS", 130)      # Safe for MiniLM 256 wordpiece token limit
CHUNK_OVERLAP_WORDS = _env_int("JKLU_CHUNK_OVERLAP", 25)
MIN_CHUNK_WORDS = 12

# ------------------------------------------------------------- retrieval
EMBED_MODEL = os.environ.get("JKLU_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
TOP_K = _env_int("JKLU_TOP_K", 8)
CANDIDATES = _env_int("JKLU_CANDIDATES", 60)         # per retriever before fusion
RRF_K = 60
W_DENSE = _env_float("JKLU_W_DENSE", 1.0)
W_SPARSE = _env_float("JKLU_W_SPARSE", 1.0)
CATEGORY_BOOST = _env_float("JKLU_CATEGORY_BOOST", 2.2)
MAX_CHUNKS_PER_DOC = 5        # allow complete fee/policy schedules across pages

# -------------------------------------------------------------- evidence
# Cosine similarity floor (only used when a real sentence-embedding model is loaded)
MIN_DENSE_SCORE = _env_float("JKLU_MIN_DENSE", 0.25)
# Share of the question's content words that must be found in the evidence
MIN_COVERAGE = _env_float("JKLU_MIN_COVERAGE", 0.50)
CLARIFY_COVERAGE = _env_float("JKLU_CLARIFY_COVERAGE", 0.34)

# ------------------------------------------------------------------ LLM
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "groq").lower()   # groq|auto|openai|anthropic|gemini|ollama|openrouter|custom|none
GROQ_MODEL = os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b")
GROQ_BASE_URL = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-5-5")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_BASE_URL = os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct")
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
CUSTOM_LLM_BASE_URL = os.environ.get("CUSTOM_LLM_BASE_URL", "")
CUSTOM_LLM_MODEL = os.environ.get("CUSTOM_LLM_MODEL", "")
LLM_TIMEOUT = _env_int("JKLU_LLM_TIMEOUT", 8)
LLM_MAX_TOKENS = _env_int("JKLU_LLM_MAX_TOKENS", 700)
MAX_HISTORY_TURNS = _env_int("JKLU_MAX_HISTORY_TURNS", 8)

# ------------------------------------------------------------ servers
API_HOST = os.environ.get("JKLU_API_HOST", "127.0.0.1")
API_PORT = _env_int("JKLU_API_PORT", 8000)
UI_PORT = _env_int("JKLU_UI_PORT", 8501)

UNIVERSITY_NAME = "JK Lakshmipat University (JKLU)"
CONTACT_PAGE = "https://jklu.edu.in/contact-us"
