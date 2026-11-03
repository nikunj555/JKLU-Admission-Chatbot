#!/usr/bin/env python3
"""Knowledge Base Pre-computation & Deployment Validator.

Runs during the Render build phase (or local setup):
1. Verifies/generates data/processed/chunks.jsonl.
2. Builds data/processed/faculty.json if missing.
3. Builds/verifies FAISS vector index, metadata.json, and bm25.pkl.
4. Pre-caches the FastEmbed ONNX embedding model into the container image.
5. Verifies KnowledgeBase loads cleanly in memory with > 0 chunks.

Exits with code 0 on success, or code 1 on failure so deployment fails loudly
with clear error messages instead of deploying an empty, unusable service.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Ensure project root is in sys.path
ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jklu import config as C
from jklu.utils import log, read_json, read_jsonl


def prepare_knowledge_base() -> bool:
    t0 = time.time()
    print("=" * 70)
    print("  JKLU Knowledge Base Preparation & Validation")
    print("=" * 70)

    # 1. Ensure required directories
    for d in (C.DATA_DIR, C.PROCESSED_DIR, C.VECTOR_DIR, C.MANUAL_DIR):
        d.mkdir(parents=True, exist_ok=True)

    # 2. Check chunks.jsonl
    chunks_ready = C.CHUNKS_PATH.is_file() and C.CHUNKS_PATH.stat().st_size > 100
    if not chunks_ready:
        print("\n[Phase 1] chunks.jsonl missing or empty. Running ingestion...")
        from jklu.ingest import run_ingestion
        summary = run_ingestion(offline=True)
        print(f"  Ingestion finished: {summary.get('documents', 0)} documents -> {summary.get('chunks', 0)} chunks")
        if not C.CHUNKS_PATH.is_file() or C.CHUNKS_PATH.stat().st_size == 0:
            print("FATAL: Ingestion failed to produce data/processed/chunks.jsonl!", file=sys.stderr)
            return False
    else:
        chunks = read_jsonl(C.CHUNKS_PATH)
        print(f"\n[Phase 1] Verified existing chunks.jsonl: {len(chunks):,} chunks ({C.CHUNKS_PATH.stat().st_size / (1024*1024):.2f} MB)")

    # 3. Check / build faculty.json
    fac_path = C.PROCESSED_DIR / "faculty.json"
    if not fac_path.is_file() or fac_path.stat().st_size == 0:
        print("\n[Phase 2] Building structured faculty index...")
        from scripts.build_faculty_index import build_faculty_index
        build_faculty_index()
    else:
        print(f"\n[Phase 2] Verified existing faculty.json ({fac_path.stat().st_size / 1024:.1f} KB)")

    # 4. Check / build Vector & BM25 index
    print("\n[Phase 3] Building / verifying FAISS & BM25 indices...")
    from jklu.index import ensure_index
    info = ensure_index(force=False, allow_semantic=True)
    print(f"  Vector store ready: {info.get('n_chunks', 0)} vectors, dim={info.get('dim', 384)}, embedder={info.get('embedder_kind', 'unknown')}")

    # 5. Pre-cache embedding model
    print("\n[Phase 4] Pre-caching FastEmbed ONNX model in container image...")
    from jklu.index import load_embedder
    embedder = load_embedder(allow_semantic=True)
    test_vec = embedder.encode(["JK Lakshmipat University admissions"])
    print(f"  Embedder initialized successfully: {embedder.name} (shape={test_vec.shape})")

    # 6. Full end-to-end verification of KnowledgeBase
    print("\n[Phase 5] Verifying KnowledgeBase load...")
    from jklu.index import KnowledgeBase
    kb = KnowledgeBase.load(allow_semantic=True)
    if not kb.chunks:
        print("FATAL: KnowledgeBase loaded 0 chunks!", file=sys.stderr)
        return False
    if kb.vi is None or kb.vi.matrix.shape[0] != len(kb.chunks):
        print(f"FATAL: VectorIndex count ({getattr(kb.vi, 'matrix', None)}) does not match chunks ({len(kb.chunks)})!", file=sys.stderr)
        return False
    if kb.bm25 is None:
        print("FATAL: BM25 index could not be loaded!", file=sys.stderr)
        return False

    elapsed = round(time.time() - t0, 2)
    print("\n" + "=" * 70)
    print(f"  SUCCESS: Knowledge base is fully built and verified in {elapsed}s.")
    print(f"  Chunks: {len(kb.chunks):,} | Embedder: {embedder.name} | FAISS: OK | BM25: OK")
    print("=" * 70 + "\n")
    return True


if __name__ == "__main__":
    success = prepare_knowledge_base()
    sys.exit(0 if success else 1)
