"""Phase 2 - embeddings, FAISS vector store, BM25 and hybrid retrieval.

Retrieval = dense semantic search (Sentence-Transformers + FAISS)
          + sparse keyword search (BM25)
          fused with Reciprocal Rank Fusion, a query-category boost,
          a source-priority/freshness prior and a per-document diversity cap.

Fallbacks (the pipeline never crashes):
  * sentence-transformers / model download unavailable -> lexical hashing embedder (still FAISS)
  * faiss not installed                                -> exact NumPy inner-product search
"""
from __future__ import annotations

import heapq
import math
import re
import time
import zlib
from datetime import datetime, timezone

import numpy as np

from . import config as C
from . import textproc as T
from .utils import file_sha256, log, read_json, read_jsonl, write_json

try:
    import faiss  # type: ignore
except Exception:  # pragma: no cover
    faiss = None


# ==========================================================================
# Embedders
# ==========================================================================
class SemanticEmbedder:
    kind = "semantic"

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer  # heavy import kept lazy
        self.name = model_name
        self.model = SentenceTransformer(model_name)
        try:
            self.model.max_seq_length = min(int(self.model.max_seq_length or 256), 256)
        except Exception:
            pass
        self.dim = int(self.model.get_sentence_embedding_dimension())

    def encode(self, texts: list[str], batch_size: int = 32, progress: bool = False) -> np.ndarray:
        emb = self.model.encode(texts, batch_size=batch_size, show_progress_bar=progress,
                                normalize_embeddings=True, convert_to_numpy=True)
        return np.ascontiguousarray(emb, dtype="float32")


class HashingEmbedder:
    """Deterministic lexical embedder (signed feature hashing of uni+bi-grams).
    Used only when a semantic model cannot be loaded, so FAISS search keeps working."""
    kind = "lexical"

    def __init__(self, dim: int = 768):
        self.name = f"hashing-{dim}"
        self.dim = dim

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype="float32")
        toks = T.tokens(text)
        grams = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
        counts: dict[str, int] = {}
        for g in grams:
            counts[g] = counts.get(g, 0) + 1
        for g, c in counts.items():
            h = zlib.crc32(g.encode("utf-8"))
            sign = 1.0 if (h >> 31) & 1 else -1.0
            v[h % self.dim] += sign * (1.0 + math.log(c))
        n = float(np.linalg.norm(v))
        return v / n if n > 0 else v

    def encode(self, texts: list[str], batch_size: int = 64, progress: bool = False) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype="float32")
        return np.ascontiguousarray(np.vstack([self._vec(t) for t in texts]), dtype="float32")


_EMBEDDER_CACHE: dict[str, object] = {}


def load_embedder(model_name: str | None = None, allow_semantic: bool = True):
    """Return a SemanticEmbedder when possible, else the HashingEmbedder."""
    model_name = model_name or C.EMBED_MODEL
    key = f"{model_name}|{allow_semantic}"
    if key in _EMBEDDER_CACHE:
        return _EMBEDDER_CACHE[key]
    emb = None
    if allow_semantic:
        try:
            log.info("Loading embedding model: %s", model_name)
            emb = SemanticEmbedder(model_name)
        except Exception as exc:
            log.warning("Semantic model unavailable (%s: %s). Falling back to lexical embeddings. "
                        "Install `sentence-transformers` and connect to the internet once to download "
                        "the model for full semantic search.", type(exc).__name__, str(exc)[:100])
    if emb is None:
        emb = HashingEmbedder()
    _EMBEDDER_CACHE[key] = emb
    return emb


def embed_text(chunk: dict) -> str:
    """Text that is embedded / BM25-indexed: title + section give each chunk context."""
    head = chunk.get("title", "")
    sec = chunk.get("section", "")
    if sec and sec.lower() != head.lower():
        head = f"{head} - {sec}"
    return f"{head}\n{chunk['text']}"


# ==========================================================================
# BM25
# ==========================================================================
class BM25:
    def __init__(self, docs: list[str], k1: float = 1.4, b: float = 0.75):
        self.k1, self.b = k1, b
        self.n = len(docs)
        self.post: dict[str, list[tuple[int, int]]] = {}
        self.dl = np.zeros(self.n, dtype="float32")
        for i, d in enumerate(docs):
            toks = T.bigram_tokens(d)   # unigrams + bigrams for phrase matching
            self.dl[i] = max(len(T.tokens(d)), 1)  # length in unigrams (for normalisation)
            tf: dict[str, int] = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            for t, c in tf.items():
                self.post.setdefault(t, []).append((i, c))
        self.avgdl = float(self.dl.mean()) if self.n else 1.0
        self.idf = {t: math.log(1.0 + (self.n - len(p) + 0.5) / (len(p) + 0.5)) for t, p in self.post.items()}

    def scores(self, terms: list[str], weights: dict[str, float] | None = None) -> np.ndarray:
        s = np.zeros(self.n, dtype="float32")
        for t in set(terms):
            plist = self.post.get(t)
            if not plist:
                continue
            w = (weights or {}).get(t, 1.0) * self.idf[t]
            for i, tf in plist:
                denom = tf + self.k1 * (1 - self.b + self.b * self.dl[i] / self.avgdl)
                s[i] += w * tf * (self.k1 + 1) / denom
        return s

    def top(self, terms: list[str], k: int, weights: dict[str, float] | None = None) -> list[tuple[int, float]]:
        s = self.scores(terms, weights)
        if not s.size:
            return []
        k = min(k, s.size)
        idx = np.argpartition(-s, k - 1)[:k] if k < s.size else np.arange(s.size)
        idx = idx[np.argsort(-s[idx])]
        return [(int(i), float(s[i])) for i in idx if s[i] > 0]


# ==========================================================================
# Vector index wrapper (FAISS, or NumPy when faiss is missing)
# ==========================================================================
class VectorIndex:
    def __init__(self, matrix: np.ndarray | None = None, index=None):
        self.matrix = matrix          # kept in memory (small corpus) for per-chunk cosine
        self.index = index

    @classmethod
    def build(cls, matrix: np.ndarray) -> "VectorIndex":
        matrix = np.ascontiguousarray(matrix, dtype="float32")
        idx = None
        if faiss is not None and matrix.shape[0] > 0:
            idx = faiss.IndexFlatIP(matrix.shape[1])   # exact inner product == cosine (normalised)
            idx.add(matrix)
        return cls(matrix, idx)

    def search(self, q: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
        k = max(1, min(k, self.matrix.shape[0]))
        q = np.ascontiguousarray(q.reshape(1, -1), dtype="float32")
        if self.index is not None:
            sc, ids = self.index.search(q, k)
            return sc[0], ids[0]
        sims = self.matrix @ q[0]
        ids = np.argsort(-sims)[:k]
        return sims[ids], ids

    def save(self, path) -> None:
        if self.index is not None:
            faiss.write_index(self.index, str(path))
        else:
            np.save(str(path) + ".npy", self.matrix)

    @classmethod
    def load(cls, path) -> "VectorIndex":
        if faiss is not None and path.is_file():
            idx = faiss.read_index(str(path))
            mat = np.ascontiguousarray(idx.reconstruct_n(0, idx.ntotal), dtype="float32")
            return cls(mat, idx)
        npy = path.with_name(path.name + ".npy")
        if npy.is_file():
            return cls.build(np.load(npy))
        raise FileNotFoundError(str(path))


# ==========================================================================
# Build / load
# ==========================================================================
def _index_signature(model_name: str) -> dict:
    return {"chunks_sha256": file_sha256(C.CHUNKS_PATH), "model": model_name}


def index_is_current(want_semantic: bool = True) -> bool:
    """True when the stored index matches chunks.jsonl (and a better embedder isn't available)."""
    info = read_json(C.INDEX_INFO_PATH)
    if not info or not C.CHUNKS_PATH.is_file() or not C.METADATA_PATH.is_file():
        return False
    if not (C.FAISS_PATH.is_file() or C.FAISS_PATH.with_name(C.FAISS_PATH.name + ".npy").is_file()):
        return False
    if info.get("chunks_sha256") != file_sha256(C.CHUNKS_PATH):
        return False
    if info.get("embedder_kind") == "lexical" and want_semantic:
        # rebuild only if a real semantic model has become available since the last build
        return load_embedder().kind != "semantic"
    return info.get("model") == C.EMBED_MODEL or info.get("embedder_kind") == "lexical"


def build_index(allow_semantic: bool = True) -> dict:
    """Embed every chunk and persist the FAISS index + metadata."""
    t0 = time.time()
    chunks = read_jsonl(C.CHUNKS_PATH)
    if not chunks:
        raise RuntimeError("chunks.jsonl is empty - run the ingestion phase first")
    embedder = load_embedder(allow_semantic=allow_semantic)
    texts = [embed_text(c) for c in chunks]
    log.info("Encoding %d chunks with %s ...", len(texts), embedder.name)
    matrix = embedder.encode(texts, progress=True) if embedder.kind == "semantic" else embedder.encode(texts)
    vi = VectorIndex.build(matrix)
    C.VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    vi.save(C.FAISS_PATH)
    write_json(C.METADATA_PATH, chunks)
    info = {
        **_index_signature(C.EMBED_MODEL),
        "embedder": embedder.name, "embedder_kind": embedder.kind, "dim": int(matrix.shape[1]),
        "n_chunks": len(chunks), "faiss": faiss is not None,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    write_json(C.INDEX_INFO_PATH, info)
    log.info("Index built: %d vectors x %d dims (%s) in %.1fs", len(chunks), matrix.shape[1],
             embedder.kind, time.time() - t0)
    return info


def ensure_index(force: bool = False, allow_semantic: bool = True) -> dict:
    if not force and index_is_current(allow_semantic):
        info = read_json(C.INDEX_INFO_PATH, {})
        log.info("Vector index is up to date (%s chunks, %s embedder)", info.get("n_chunks"), info.get("embedder_kind"))
        return info
    return build_index(allow_semantic=allow_semantic)


# ==========================================================================
# Knowledge base: hybrid search
# ==========================================================================
def _start_year(ay: str | None) -> int | None:
    m = re.match(r"(20\d{2})", ay or "")
    return int(m.group(1)) if m else None


class KnowledgeBase:
    def __init__(self):
        self.chunks: list[dict] = []
        self.vi: VectorIndex | None = None
        self.bm25: BM25 | None = None
        self.embedder = None
        self.info: dict = {}
        self._prior: np.ndarray | None = None

    # ------------------------------------------------------------ loading
    @classmethod
    def load(cls, allow_semantic: bool = True) -> "KnowledgeBase":
        kb = cls()
        kb.info = read_json(C.INDEX_INFO_PATH, {}) or {}
        kb.chunks = read_json(C.METADATA_PATH, []) or []
        if not kb.chunks:
            raise RuntimeError("Knowledge base is empty. Run `python run.py` to build it.")
        kb.vi = VectorIndex.load(C.FAISS_PATH)
        if kb.vi.matrix.shape[0] != len(kb.chunks):
            raise RuntimeError("Index and metadata are out of sync. Run `python run.py --rebuild`.")
        built_kind = kb.info.get("embedder_kind", "semantic")
        if built_kind == "semantic" and allow_semantic:
            kb.embedder = load_embedder(kb.info.get("model") or C.EMBED_MODEL)
            if kb.embedder.kind != "semantic":      # model vanished: dense search is meaningless
                kb.embedder = None
        # Load or build BM25 index with disk caching
        bm25_path = C.VECTOR_DIR / "bm25.pkl"
        if bm25_path.is_file():
            try:
                import pickle
                with open(bm25_path, "rb") as f:
                    kb.bm25 = pickle.load(f)
            except Exception:
                kb.bm25 = None
        if kb.bm25 is None or getattr(kb.bm25, "n", 0) != len(kb.chunks):
            import pickle
            kb.bm25 = BM25([embed_text(c) for c in kb.chunks])
            try:
                with open(bm25_path, "wb") as f:
                    pickle.dump(kb.bm25, f)
            except Exception:
                pass
        kb._prior = kb._compute_prior()
        kb.chunks_by_id = {c.get("chunk_id", ""): c for c in kb.chunks if c.get("chunk_id")}
        return kb

    def get_chunk(self, chunk_id: str) -> dict | None:
        return getattr(self, "chunks_by_id", {}).get(chunk_id)

    def _compute_prior(self) -> np.ndarray:
        years = [y for y in (_start_year(c.get("academic_year")) for c in self.chunks) if y]
        newest = max(years) if years else None
        prior = np.ones(len(self.chunks), dtype="float32")
        for i, c in enumerate(self.chunks):
            f = 1.0 + 0.04 * (int(c.get("priority", 2)) - 2)           # core sources slightly favoured
            y = _start_year(c.get("academic_year"))
            if newest and y and y < newest:                             # stale academic year penalty
                f *= max(0.8, 1.0 - 0.05 * (newest - y))
            prior[i] = f
        return prior

    @property
    def semantic(self) -> bool:
        return self.embedder is not None and self.embedder.kind == "semantic"

    # ------------------------------------------------------------- search
    def search(self, query: str, top_k: int = C.TOP_K, category: str | None = None,
               mode: str = "hybrid") -> dict:
        """Return {'results': [...], 'routed': [...], 'semantic': bool, ...}."""
        query = (query or "").strip()
        n = len(self.chunks)
        out = {"results": [], "routed": [], "semantic": self.semantic, "terms": []}
        if not query or n == 0:
            return out
        terms = T.content_terms(query)
        out["terms"] = terms
        routed = [category] if category else T.route_categories(query)
        out["routed"] = routed
        allowed = None
        if category:
            allowed = np.array([c.get("category") == category for c in self.chunks])

        cand_k = n if (category or n <= 3000) else C.CANDIDATES
        cand_k = min(max(cand_k, C.CANDIDATES), n)

        dense_rank: dict[int, int] = {}
        dense_cos: dict[int, float] = {}
        qvec = None
        if mode in ("hybrid", "dense") and self.embedder is not None:
            qvec = self.embedder.encode([query])[0]
            sc, ids = self.vi.search(qvec, cand_k)
            r = 0
            for s, i in zip(sc, ids):
                if i < 0 or (allowed is not None and not allowed[i]):
                    continue
                dense_rank[int(i)] = r = r + 1
                dense_cos[int(i)] = float(s)
                if r >= C.CANDIDATES:
                    break

        sparse_rank: dict[int, int] = {}
        sparse_score: dict[int, float] = {}
        if mode in ("hybrid", "sparse", "keyword"):
            exp = T.expand_terms(terms)
            # add bigrams from the original query for phrase matching in the BM25 index
            q_bigrams = [f"{a}__{b}" for a, b in zip(terms, terms[1:])]
            exp = exp + [bg for bg in q_bigrams if bg not in set(exp)]
            weights = {t: 0.5 for t in exp if t not in terms}      # synonyms count less
            # bigrams get a small extra boost (they indicate exact phrase)
            for bg in q_bigrams:
                weights[bg] = 1.2
            primary_terms = [t for t in terms if t not in T.GENERIC_HEAD_STEMS]
            raw_scores = self.bm25.scores(exp, weights)
            if primary_terms and n > 0:
                hits = np.zeros(n, dtype="int32")
                for pt in primary_terms:
                    plist = self.bm25.post.get(pt)
                    if plist:
                        for idx, _ in plist:
                            hits[idx] += 1
                n_pt = len(primary_terms)
                raw_scores[hits == n_pt] *= 2.5
                raw_scores[(hits > 0) & (hits < n_pt)] *= 1.5

            r = 0
            k_cand = min(n, cand_k * 2)
            top_idx = np.argpartition(-raw_scores, min(k_cand - 1, len(raw_scores) - 1))[:k_cand] if k_cand < len(raw_scores) else np.arange(len(raw_scores))
            top_idx = top_idx[np.argsort(-raw_scores[top_idx])]
            for i in top_idx:
                s = float(raw_scores[i])
                if s <= 0:
                    break
                if allowed is not None and not allowed[i]:
                    continue
                sparse_rank[int(i)] = r = r + 1
                sparse_score[int(i)] = s
                if r >= C.CANDIDATES:
                    break

        fused: dict[int, float] = {}
        wd = C.W_DENSE if self.semantic else C.W_DENSE * 0.6      # lexical embeddings are weaker
        for i, rk in dense_rank.items():
            fused[i] = fused.get(i, 0.0) + wd / (C.RRF_K + rk)
        for i, rk in sparse_rank.items():
            fused[i] = fused.get(i, 0.0) + C.W_SPARSE / (C.RRF_K + rk)

        boost_cats = set(routed)
        for i in list(fused):
            f = self._prior[i]
            cat_i = self.chunks[i].get("category")
            if routed and cat_i in boost_cats and not category:
                f *= C.CATEGORY_BOOST if cat_i == routed[0] else 1 + (C.CATEGORY_BOOST - 1) * 0.6
            fused[i] *= f

        ordered = [i for i, _ in heapq.nlargest(max(top_k * 6, 30), fused.items(), key=lambda kv: kv[1])]
        per_doc: dict[str, int] = {}
        results: list[dict] = []
        for i in ordered:
            c = self.chunks[i]
            if per_doc.get(c["doc_id"], 0) >= C.MAX_CHUNKS_PER_DOC:
                continue
            per_doc[c["doc_id"]] = per_doc.get(c["doc_id"], 0) + 1
            rec = dict(c)
            rec["rank"] = len(results) + 1
            rec["fused_score"] = float(fused[i])
            rec["sparse_score"] = float(sparse_score.get(i, 0.0))
            if qvec is not None:
                rec["dense_score"] = float(dense_cos.get(i, float(self.vi.matrix[i] @ qvec)))
            else:
                rec["dense_score"] = None
            # kept for backwards compatibility with the old Phase-2 field name
            rec["similarity_score"] = rec["dense_score"] if rec["dense_score"] is not None else rec["fused_score"]
            results.append(rec)
            if len(results) >= top_k:
                break
        out["results"] = results
        return out


if __name__ == "__main__":
    ensure_index()
