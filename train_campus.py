#!/usr/bin/env python3
"""Train the JKLU chatbot on campus documents (e.g. from Downloads/campus or data/manual).

Usage:
    python train_campus.py
    python train_campus.py "C:\\path\\to\\campus"
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from jklu import config as C
from jklu.index import build_index, KnowledgeBase
from jklu.ingest import run_ingestion
from jklu.utils import log


def main():
    target_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"c:\Users\Nikunj katta\Downloads\campus")
    print("=" * 72)
    print("  JKLU Chatbot - Campus Knowledge Training")
    print("=" * 72)

    if not target_dir.is_dir():
        print(f"\n[Warning] Directory not found: {target_dir}")
        print("Checking data/manual directory instead...")
        target_dir = C.MANUAL_DIR

    print(f"\n[1/3] Scanning folder: {target_dir}")
    supported_exts = {".pdf", ".docx", ".txt", ".md", ".html", ".htm", ".csv", ".json"}
    files = [p for p in target_dir.rglob("*") if p.is_file() and p.suffix.lower() in supported_exts]

    if not files:
        print(f"No supported document files found in {target_dir}")
        print(f"Supported formats: {', '.join(sorted(supported_exts))}")
    else:
        print(f"Found {len(files)} document(s):")
        for f in files:
            size_kb = f.stat().st_size / 1024
            print(f"  • {f.name:<40} ({size_kb:.1f} KB) [{f.suffix.lower()}]")

    # Ingest: offline mode preserves cached web docs and ingests manual + campus documents
    print("\n[2/3] Processing documents and building chunks...")
    t0 = time.time()
    summary = run_ingestion(offline=True)
    print(f"  Total documents : {summary['documents']}")
    print(f"  Total chunks    : {summary['chunks']}")
    print("  Chunks by category:")
    for cat, n in summary.get("chunks_per_category", {}).items():
        print(f"    - {cat:<15}: {n:>5} chunks")

    # Phase 2: Vector index rebuild
    print("\n[3/3] Generating embeddings & rebuilding FAISS vector index...")
    idx_info = build_index(allow_semantic=True)
    print(f"  Vectors indexed : {idx_info.get('n_chunks')}")
    print(f"  Embedding model : {idx_info.get('embedder')}")
    print(f"  Elapsed time    : {time.time() - t0:.1f}s")

    # Verification search
    print("\n[Verification] Testing knowledge retrieval for 'campus'...")
    try:
        kb = KnowledgeBase.load()
        results = kb.search("campus facilities and layout", top_k=3)["results"]
        if results:
            print("  Top retrieved document:")
            print(f"    Title  : {results[0].get('title')}")
            print(f"    Source : {results[0].get('source_url')}")
            snippet = results[0].get('text', '')[:160].replace('\n', ' ')
            print(f"    Preview: {snippet}...")
            print("\n  Training completed successfully! The bot now knows your campus data.")
        else:
            print("  Warning: No results retrieved. Please check document content.")
    except Exception as exc:
        print(f"  Verification note: {exc}")

    print("\nStart the chatbot now with:")
    print("  python run.py --skip-ingest")
    print("=" * 72)


if __name__ == "__main__":
    main()
