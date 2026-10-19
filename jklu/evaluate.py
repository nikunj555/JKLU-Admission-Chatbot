"""Phase 8 - experimental evaluation.

Compares  A) keyword search (TF-IDF)   B) dense-only   C) proposed hybrid RAG retrieval
and measures the full agent's answer/clarify/escalate behaviour.

Retrieval metrics (answerable questions): Hit@K, Precision@K, MRR, Evidence-Recall@K
Agent metrics: status accuracy, hallucination-rejection rate (irrelevant/unsupported -> escalate),
               answer rate on answerable questions, clarification accuracy.
"""
from __future__ import annotations

import csv
import json
import time
from collections import defaultdict

from . import config as C
from . import evidence as E
from .agent import JKLUAgent
from .index import KnowledgeBase
from .utils import log, write_json

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
except Exception:  # pragma: no cover
    TfidfVectorizer = None


def load_questions() -> list[dict]:
    if not C.TEST_QUESTIONS_PATH.is_file():
        return []
    with open(C.TEST_QUESTIONS_PATH, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _groups(spec: str) -> list[list[str]]:
    return [[a.strip().lower() for a in g.split("|") if a.strip()] for g in (spec or "").split("&") if g.strip()]


def _matches(chunk: dict, alts: list[str]) -> bool:
    hay = f"{chunk.get('source_url', '')} {chunk.get('title', '')}".lower()
    return any(a in hay for a in alts)


class TfidfBaseline:
    """System A: classic keyword search (TF-IDF cosine over chunk text)."""

    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        if TfidfVectorizer is None:
            raise RuntimeError("scikit-learn missing")
        self.vec = TfidfVectorizer(stop_words="english", lowercase=True, ngram_range=(1, 1), sublinear_tf=True)
        self.mat = self.vec.fit_transform([f"{c['title']} {c['text']}" for c in chunks])

    def search(self, q: str, k: int) -> list[dict]:
        sims = linear_kernel(self.vec.transform([q]), self.mat).ravel()
        order = sims.argsort()[::-1][:k]
        return [self.chunks[i] for i in order if sims[i] > 0]


def _retrieval_metrics(rows: list[dict], k: int) -> dict:
    n = len(rows)
    if not n:
        return {"n": 0}
    return {
        "n": n,
        f"hit@{k}": round(sum(r["hit"] for r in rows) / n, 3),
        f"precision@{k}": round(sum(r["precision"] for r in rows) / n, 3),
        "mrr": round(sum(r["rr"] for r in rows) / n, 3),
        f"evidence_recall@{k}": round(sum(r["terms_ok"] for r in rows) / n, 3),
    }


def evaluate(top_k: int = C.TOP_K, calibrate: bool = False) -> dict:
    questions = load_questions()
    if not questions:
        log.warning("No test questions found at %s", C.TEST_QUESTIONS_PATH)
        return {}
    kb = KnowledgeBase.load()
    agent = JKLUAgent(kb)
    tfidf = None
    try:
        tfidf = TfidfBaseline(kb.chunks)
    except Exception as exc:
        log.warning("TF-IDF baseline unavailable (%s); using BM25 as keyword baseline", exc)

    systems = {
        "A_keyword": lambda q: tfidf.search(q, top_k) if tfidf else kb.search(q, top_k, mode="sparse")["results"],
        "B_dense": lambda q: kb.search(q, top_k, mode="dense")["results"],
        "C_hybrid_rag": lambda q: kb.search(q, top_k, mode="hybrid")["results"],
    }
    per_sys: dict[str, list[dict]] = {s: [] for s in systems}
    skipped: list[str] = []
    detail: list[dict] = []
    search_cache: dict[int, dict] = {}

    for qi, q in enumerate(questions):
        question, qtype = q["question"], q["type"]
        groups = _groups(q.get("expected_source", ""))
        terms = [t.strip().lower() for t in (q.get("expected_terms") or "").split(";") if t.strip()]
        row = {"id": q["id"], "type": qtype, "question": question, "expected_status": q["expected_status"]}

        # --- agent-level behaviour (all questions)
        search_cache[qi] = kb.search(question, top_k)
        resp = agent.ask(question, top_k=top_k)
        row.update(status=resp["status"], confidence=resp["confidence"], reason=resp["reason"],
                   status_ok=resp["status"] == q["expected_status"],
                   provider=resp.get("provider"), top_source=(resp["sources"][0]["url"] if resp["sources"] else ""))

        # --- retrieval-level metrics (answerable questions with a known source)
        if groups and q["expected_status"] == "answer":
            if any(not any(_matches(c, g) for c in kb.chunks) for g in groups):
                skipped.append(f"#{q['id']} {question} (source not in knowledge base)")
                row["retrieval"] = "skipped: expected source not in KB"
            else:
                for name, fn in systems.items():
                    res = fn(question)
                    hit = all(any(_matches(c, g) for c in res) for g in groups)
                    flat = [a for g in groups for a in g]
                    rel = [_matches(c, flat) for c in res]
                    rr = next((1.0 / (i + 1) for i, r in enumerate(rel) if r), 0.0)
                    blob = " ".join(c["text"] for c in res).lower()
                    per_sys[name].append({
                        "type": qtype, "hit": float(hit), "precision": (sum(rel) / len(res)) if res else 0.0,
                        "rr": rr, "terms_ok": float(all(t in blob for t in terms)) if terms else float(hit)})
                    row[f"{name}_hit"] = int(hit)
        detail.append(row)

    summary: dict = {"top_k": top_k, "n_questions": len(questions), "kb_chunks": len(kb.chunks),
                     "retrieval_mode": "semantic+bm25" if kb.semantic else "lexical+bm25", "skipped": skipped}
    summary["retrieval"] = {s: _retrieval_metrics(rows, top_k) for s, rows in per_sys.items()}
    by_type: dict[str, dict] = {}
    for name, rows in per_sys.items():
        groups_by_type: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            groups_by_type[r["type"]].append(r)
        by_type[name] = {t: _retrieval_metrics(v, top_k) for t, v in groups_by_type.items()}
    summary["retrieval_by_type"] = by_type

    ok = [d for d in detail if d["status_ok"]]
    answerable = [d for d in detail if d["expected_status"] == "answer"]
    should_refuse = [d for d in detail if d["expected_status"] == "escalate"]
    should_clarify = [d for d in detail if d["expected_status"] == "clarify"]
    pct = lambda a, b: round(len(a) / len(b), 3) if b else None  # noqa: E731
    summary["agent"] = {
        "status_accuracy": pct(ok, detail),
        "answer_rate_on_answerable": pct([d for d in answerable if d["status"] == "answer"], answerable),
        "hallucination_rejection_rate": pct([d for d in should_refuse if d["status"] != "answer"], should_refuse),
        "clarification_accuracy": pct([d for d in should_clarify if d["status"] == "clarify"], should_clarify),
        "false_answers_on_unanswerable": sum(1 for d in should_refuse if d["status"] == "answer"),
    }

    # --- optional: direct-LLM baseline (needs an API key)
    if agent.generator.provider != "none":
        refuse_rx = ("don't have", "do not have", "cannot", "can't", "not aware", "unable", "no information")
        direct = []
        for q in questions:
            if q["type"] in ("irrelevant", "unsupported"):
                a = agent.generator.direct(q["question"])
                if a is not None:
                    direct.append(any(x in a.lower() for x in refuse_rx))
        if direct:
            summary["direct_llm_baseline"] = {"refusal_rate_on_unanswerable": round(sum(direct) / len(direct), 3),
                                              "n": len(direct)}

    C.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    write_json(C.RESULTS_DIR / "evaluation_summary.json", summary)
    keys = sorted({k for d in detail for k in d})
    with open(C.RESULTS_DIR / "evaluation_details.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(detail)
    _write_markdown(summary, detail)
    if calibrate:
        summary["calibration"] = _calibrate(kb, questions, search_cache)
        write_json(C.RESULTS_DIR / "evaluation_summary.json", summary)
    return summary


def _calibrate(kb: KnowledgeBase, questions: list[dict], cache: dict[int, dict]) -> dict:
    """Grid-search evidence thresholds against the labelled test set (no re-retrieval needed)."""
    best = (-1.0, None)
    old = (C.MIN_COVERAGE, C.MIN_DENSE_SCORE, C.CLARIFY_COVERAGE)
    dense_grid = [0.2, 0.25, 0.3, 0.35, 0.4, 0.45] if kb.semantic else [0.0]
    try:
        for cov in [x / 100 for x in range(30, 80, 5)]:
            for dn in dense_grid:
                C.MIN_COVERAGE, C.MIN_DENSE_SCORE, C.CLARIFY_COVERAGE = cov, dn, max(0.2, cov - 0.16)
                good = 0
                for qi, q in enumerate(questions):
                    st = E.check(q["question"], cache[qi], kb).status
                    good += st == q["expected_status"]
                acc = good / len(questions)
                if acc > best[0]:
                    best = (acc, {"JKLU_MIN_COVERAGE": cov, "JKLU_MIN_DENSE": dn})
    finally:
        C.MIN_COVERAGE, C.MIN_DENSE_SCORE, C.CLARIFY_COVERAGE = old
    log.info("Calibration: best status accuracy %.2f with %s", best[0], best[1])
    return {"best_status_accuracy": round(best[0], 3), "suggested_env": best[1]}


def _write_markdown(s: dict, detail: list[dict]) -> None:
    k = s["top_k"]
    lines = [f"# JKLU Agent - Evaluation Report", "",
             f"- Questions: **{s['n_questions']}**  |  Knowledge-base chunks: **{s['kb_chunks']}**  |  "
             f"Retrieval: **{s['retrieval_mode']}**  |  Top-K: **{k}**", "",
             "## Retrieval comparison (answerable questions)", "",
             f"| System | n | Hit@{k} | Precision@{k} | MRR | Evidence-Recall@{k} |", "|---|---|---|---|---|---|"]
    for name, m in s["retrieval"].items():
        if m.get("n"):
            lines.append(f"| {name} | {m['n']} | {m[f'hit@{k}']} | {m[f'precision@{k}']} | {m['mrr']} | "
                         f"{m[f'evidence_recall@{k}']} |")
    lines += ["", "## Agent behaviour (answer / clarify / escalate)", ""]
    for key, val in s["agent"].items():
        lines.append(f"- **{key.replace('_', ' ')}**: {val}")
    if s.get("direct_llm_baseline"):
        lines.append(f"- **direct LLM (no retrieval) refusal rate on unanswerable**: "
                     f"{s['direct_llm_baseline']['refusal_rate_on_unanswerable']}")
    if s["skipped"]:
        lines += ["", "## Skipped (source not in the current knowledge base)", ""] + [f"- {x}" for x in s["skipped"]]
    bad = [d for d in detail if not d["status_ok"]]
    if bad:
        lines += ["", "## Questions where the agent's decision differed from the label", ""]
        for d in bad:
            lines.append(f"- #{d['id']} ({d['type']}) \"{d['question']}\" -> **{d['status']}** "
                         f"(expected {d['expected_status']}); {d['reason']}")
    (C.RESULTS_DIR / "evaluation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-k", type=int, default=C.TOP_K)
    ap.add_argument("--calibrate", action="store_true")
    a = ap.parse_args()
    t = time.time()
    print(json.dumps(evaluate(a.top_k, a.calibrate), indent=2))
    print(f"done in {time.time() - t:.1f}s -> {C.RESULTS_DIR}")
