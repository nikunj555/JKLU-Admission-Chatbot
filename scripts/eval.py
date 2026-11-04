#!/usr/bin/env python3
"""Comprehensive Evaluation Framework for JKLU Assistant.

Evaluates against data/eval/gold.jsonl:
1. Retrieval: Hit@1, Hit@3, Hit@5.
2. Fact-Recall: percentage of expected ground-truth facts recalled in answers.
3. Wrong-Answer Rate: hallucinations on unanswerable queries + false escalations on answerables.
4. Correct-Refusal Rate: percentage of unanswerable questions properly refused (escalated).
5. Latency breakdown: p50 and p95 per stage and end-to-end.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jklu import config as C
from jklu.agent import JKLUAgent
from jklu.utils import read_jsonl

GOLD_PATH = ROOT / "data" / "eval" / "gold.jsonl"


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    return float(np.percentile(values, p))


def check_source_hit(sources: list[dict], expected_source: str, k: int) -> bool:
    if not expected_source or expected_source.lower() == "none":
        return False
    exp = expected_source.lower()
    for s in sources[:k]:
        title = (s.get("title") or "").lower()
        url = (s.get("url") or "").lower()
        cat = (s.get("category") or "").lower()
        snippet = (s.get("snippet") or s.get("text") or "").lower()
        if exp in title or exp in url or exp in cat or exp in snippet:
            return True
        # If expected is faculty, any faculty source is a hit
        if exp == "faculty" and (cat == "faculty" or "faculty" in url or "faculty" in title):
            return True
    return False


def check_fact_recall(answer: str, expected_facts: list[str]) -> tuple[int, int]:
    if not expected_facts:
        return 0, 0
    ans_clean = answer.lower()
    found = 0
    for fact in expected_facts:
        f_clean = fact.lower().strip()
        # Clean currency/comma patterns like "2,84,000" -> "284000" or direct match
        if f_clean in ans_clean:
            found += 1
        elif "," in f_clean and f_clean.replace(",", "") in ans_clean.replace(",", ""):
            found += 1
        elif re.search(r"\b" + re.escape(f_clean) + r"\b", ans_clean):
            found += 1
    return found, len(expected_facts)


def run_evaluation(output_md: Path | None = None, limit: int | None = None) -> dict[str, Any]:
    print("=" * 72)
    print("  JKLU Admission Assistant - Full Pipeline Evaluation")
    print("=" * 72)

    rows = read_jsonl(GOLD_PATH)
    if limit:
        rows = rows[:limit]
    print(f"Loaded {len(rows)} gold evaluation questions from {GOLD_PATH}\n")

    t_init_start = time.perf_counter()
    agent = JKLUAgent()
    init_latency_s = round(time.perf_counter() - t_init_start, 2)
    print(f"Agent loaded in {init_latency_s}s (chunks={len(agent.kb.chunks):,})\n")

    hits_at_1 = 0
    hits_at_3 = 0
    hits_at_5 = 0
    answerable_count = 0
    unanswerable_count = 0
    correct_refusals = 0
    wrong_answers = 0

    total_expected_facts = 0
    total_recalled_facts = 0

    stage_timings: dict[str, list[float]] = defaultdict(list)
    total_latencies: list[float] = []
    category_stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "correct": 0, "facts_found": 0, "facts_total": 0})

    results_log = []

    for idx, row in enumerate(rows, 1):
        q = row["question"]
        is_ans = row.get("answerable", True)
        exp_facts = row.get("expected_facts", [])
        exp_source = row.get("expected_source", "")
        cat = row.get("category", "general")
        history = row.get("history")

        t0 = time.perf_counter()
        res = agent.ask(q, history=history)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        total_latencies.append(elapsed_ms)

        # Collect stage timings
        timings = res.get("timings") or {}
        for stage, val in timings.items():
            if isinstance(val, (int, float)):
                stage_timings[stage].append(float(val))

        status = res.get("status", "answer")
        answer = res.get("answer", "")
        sources = res.get("sources", [])

        # Quality scoring
        item_result = {
            "id": row.get("id", idx),
            "question": q,
            "category": cat,
            "status": status,
            "latency_ms": elapsed_ms,
            "hit_at_1": False,
            "hit_at_3": False,
            "hit_at_5": False,
            "facts_recalled": 0,
            "facts_total": len(exp_facts),
            "verdict": "pass",
        }

        category_stats[cat]["count"] += 1

        if is_ans:
            answerable_count += 1
            h1 = check_source_hit(sources, exp_source, 1)
            h3 = check_source_hit(sources, exp_source, 3)
            h5 = check_source_hit(sources, exp_source, 5)
            if h1: hits_at_1 += 1
            if h3: hits_at_3 += 1
            if h5: hits_at_5 += 1
            item_result["hit_at_1"] = h1
            item_result["hit_at_3"] = h3
            item_result["hit_at_5"] = h5

            f_found, f_tot = check_fact_recall(answer, exp_facts)
            total_recalled_facts += f_found
            total_expected_facts += f_tot
            item_result["facts_recalled"] = f_found
            category_stats[cat]["facts_found"] += f_found
            category_stats[cat]["facts_total"] += f_tot

            if status == "escalate":
                # False refusal on an answerable question
                wrong_answers += 1
                item_result["verdict"] = "fail (false refusal)"
            elif f_tot > 0 and f_found == 0:
                # 0 facts recalled = incomplete or wrong
                wrong_answers += 1
                item_result["verdict"] = "fail (0 facts recalled)"
            else:
                category_stats[cat]["correct"] += 1
        else:
            unanswerable_count += 1
            if status == "escalate":
                correct_refusals += 1
                category_stats[cat]["correct"] += 1
                item_result["verdict"] = "pass (correct refusal)"
            else:
                # Hallucinated or answered an unanswerable question!
                wrong_answers += 1
                item_result["verdict"] = "fail (hallucination / false answer)"

        results_log.append(item_result)
        prefix = f"[{idx:03d}/{len(rows):03d}]"
        print(f"{prefix} ({cat:<12}) {q[:44]:<46} -> {status:<8} ({elapsed_ms:5.1f}ms) [{item_result['verdict']}]")

    # Metrics computation
    hit1_pct = round((hits_at_1 / max(answerable_count, 1)) * 100, 1)
    hit3_pct = round((hits_at_3 / max(answerable_count, 1)) * 100, 1)
    hit5_pct = round((hits_at_5 / max(answerable_count, 1)) * 100, 1)
    fact_recall_pct = round((total_recalled_facts / max(total_expected_facts, 1)) * 100, 1)
    wrong_answer_pct = round((wrong_answers / max(len(rows), 1)) * 100, 1)
    refusal_pct = round((correct_refusals / max(unanswerable_count, 1)) * 100, 1)

    latency_p50 = round(percentile(total_latencies, 50), 1)
    latency_p95 = round(percentile(total_latencies, 95), 1)
    latency_mean = round(float(np.mean(total_latencies)), 1)

    stage_summary = {}
    for stg, vals in stage_timings.items():
        if vals:
            stage_summary[stg] = {
                "p50": round(percentile(vals, 50), 1),
                "p95": round(percentile(vals, 95), 1),
                "mean": round(float(np.mean(vals)), 1),
            }

    report = {
        "total_questions": len(rows),
        "answerable_questions": answerable_count,
        "unanswerable_questions": unanswerable_count,
        "hit_at_1_pct": hit1_pct,
        "hit_at_3_pct": hit3_pct,
        "hit_at_5_pct": hit5_pct,
        "fact_recall_pct": fact_recall_pct,
        "wrong_answer_pct": wrong_answer_pct,
        "correct_refusal_pct": refusal_pct,
        "latency_ms": {
            "p50": latency_p50,
            "p95": latency_p95,
            "mean": latency_mean,
        },
        "stage_timings": stage_summary,
        "category_stats": dict(category_stats),
        "results_log": results_log,
    }

    # Format Markdown Report
    md_lines = [
        "# JKLU Assistant - Evaluation Report",
        "",
        f"**Date**: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}  ",
        f"**Total Questions**: {len(rows)} ({answerable_count} Answerable, {unanswerable_count} Unanswerable)  ",
        f"**Embedding Model**: FastEmbed (ONNX) `all-MiniLM-L6-v2`  ",
        f"**LLM Provider**: `{agent.generator.provider}` (`{agent.generator.model}`)  ",
        "",
        "## 1. Overall RAG Quality & Accuracy Metrics",
        "",
        "| Metric | Target | Result | Status |",
        "| :--- | :---: | :---: | :---: |",
        f"| **Retrieval Hit@1** | $\\ge 70\\%$ | **{hit1_pct}%** | {'✅' if hit1_pct >= 70 else '⚠️'} |",
        f"| **Retrieval Hit@3** | $\\ge 85\\%$ | **{hit3_pct}%** | {'✅' if hit3_pct >= 85 else '⚠️'} |",
        f"| **Retrieval Hit@5** | $\\ge 90\\%$ | **{hit5_pct}%** | {'✅' if hit5_pct >= 90 else '⚠️'} |",
        f"| **Answer Fact-Recall** | $\\ge 80\\%$ | **{fact_recall_pct}%** | {'✅' if fact_recall_pct >= 80 else '⚠️'} |",
        f"| **Wrong-Answer Rate** | $\\le 15\\%$ | **{wrong_answer_pct}%** | {'✅' if wrong_answer_pct <= 15 else '⚠️'} |",
        f"| **Unanswerable Refusal Rate** | $\\ge 80\\%$ | **{refusal_pct}%** | {'✅' if refusal_pct >= 80 else '⚠️'} |",
        "",
        "## 2. Latency Breakdown per Stage",
        "",
        "| Stage | p50 (ms) | p95 (ms) | Mean (ms) |",
        "| :--- | :---: | :---: | :---: |",
        f"| **End-to-End Latency** | **{latency_p50}** | **{latency_p95}** | **{latency_mean}** |",
    ]

    for stg, vals in sorted(stage_summary.items(), key=lambda x: -x[1]["mean"]):
        md_lines.append(f"| `{stg}` | {vals['p50']} | {vals['p95']} | {vals['mean']} |")

    md_lines.extend([
        "",
        "## 3. Breakdown by Category",
        "",
        "| Category | Questions | Correct | Fact Recall | Accuracy |",
        "| :--- | :---: | :---: | :---: | :---: |",
    ])

    for cat, stat in sorted(category_stats.items()):
        cnt = stat["count"]
        cor = stat["correct"]
        f_found = stat["facts_found"]
        f_tot = stat["facts_total"]
        f_pct = round((f_found / max(f_tot, 1)) * 100, 1) if f_tot > 0 else 100.0
        acc_pct = round((cor / max(cnt, 1)) * 100, 1)
        md_lines.append(f"| **{cat}** | {cnt} | {cor} | {f_pct}% | {acc_pct}% |")

    md_lines.extend([
        "",
        "## 4. Notable Failures & Regressions",
        "",
    ])

    fails = [r for r in results_log if "fail" in r["verdict"]]
    if not fails:
        md_lines.append("_None! All queries passed validation._\n")
    else:
        for f in fails[:15]:
            md_lines.append(f"- **[{f['category']}]** `{f['question']}` -> *Status*: `{f['status']}` | *Verdict*: `{f['verdict']}`")

    markdown_text = "\n".join(md_lines) + "\n"

    if output_md:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(markdown_text, encoding="utf-8")
        print(f"\nWritten evaluation report to {output_md}")

    return report


if __name__ == "__main__":
    out_path = ROOT / "docs" / "eval_baseline.md"
    run_evaluation(output_md=out_path)

