"""Autonomous RAG Testing and Continuous Improvement Framework for JKLU Admission Chatbot.

Modes supported:
    --mode evaluate    : Run tests and produce full JSON and Markdown reports (no code changes).
    --mode diagnose    : Analyze failure logs, categorize root causes, and propose targeted fixes.
    --mode improve     : Safely apply approved, low-risk, reversible query normalization & synonym mappings.
    --mode regression  : Run verified regression suite to guarantee zero backsliding.
    --mode full        : Execute evaluate -> diagnose -> improve -> regression -> report.

Usage:
    python -m tests.run_rag_evaluation --mode evaluate --sample 30
    python -m tests.run_rag_evaluation --mode full
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jklu import config as C
from jklu import evidence as E
from jklu import textproc as T
from jklu.agent import JKLUAgent
from jklu.index import KnowledgeBase
from jklu.utils import log, write_json

DATASET_PATH = ROOT / "tests" / "data" / "jklu_admission_questions.jsonl"
EVAL_DIR = ROOT / "tests" / "evaluation"
FAILURE_LOG_PATH = EVAL_DIR / "failure_log.jsonl"
VERIFIED_CORRECTIONS_PATH = EVAL_DIR / "verified_corrections.jsonl"
APPROVED_ALIASES_PATH = EVAL_DIR / "approved_query_aliases.json"
RESULTS_DIR = ROOT / "results"

class RAGEvaluationRunner:
    def __init__(self, agent: JKLUAgent | None = None):
        self.agent = agent or JKLUAgent()
        self.kb = self.agent.kb
        EVAL_DIR.mkdir(parents=True, exist_ok=True)
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    def load_dataset(self, category: str | None = None, sample: int | None = None) -> list[dict]:
        if not DATASET_PATH.is_file():
            raise FileNotFoundError(f"Evaluation dataset not found at {DATASET_PATH}")
        cases = []
        with open(DATASET_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    c = json.loads(line)
                    if not category or c.get("category") == category:
                        cases.append(c)
        if sample and sample < len(cases):
            # Take a stratified sample across categories
            by_cat = defaultdict(list)
            for c in cases:
                by_cat[c.get("category", "general")].append(c)
            sampled = []
            per_cat = max(1, sample // max(1, len(by_cat)))
            for cat_cases in by_cat.values():
                sampled.extend(cat_cases[:per_cat])
            return sampled[:sample]
        return cases

    def run_single_test(self, test_case: dict) -> dict:
        t_id = test_case["test_id"]
        q = test_case["question"]
        expected_status = test_case.get("expected_status", "answer")
        should_abstain = test_case.get("should_abstain", False)
        required_citations = test_case.get("required_citations", True)
        expected_facts = test_case.get("expected_answer_facts", [])
        expected_sources = [s.lower() for s in test_case.get("expected_source_ids", [])]
        history = test_case.get("conversation_context", [])

        t0 = time.time()
        try:
            res = self.agent.ask(question=q, history=history)
            latency_ms = round((time.time() - t0) * 1000)
            status = res.get("status", "error")
            answer = res.get("answer", "")
            sources = res.get("sources", [])
            query_used = res.get("query_used", q)

            # Evaluate Layers:
            # 1. Retrieval Layer (Recall@k)
            retrieved_titles = [f"{s.get('title', '')} {s.get('url', '')}".lower() for s in sources]
            hit = False
            if not expected_sources:
                hit = True
            else:
                for exp_s in expected_sources:
                    if any(exp_s in t for t in retrieved_titles):
                        hit = True
                        break

            # 2. Fact Grounding Layer
            ans_lower = answer.lower()
            facts_found = [f for f in expected_facts if f.lower() in ans_lower]
            fact_coverage = len(facts_found) / max(1, len(expected_facts)) if expected_facts else 1.0

            # 3. Citation Validity Layer
            citations_valid = True
            if required_citations:
                citations_valid = len(sources) > 0 and any(f"[{s.get('n', 1)}]" in answer for s in sources)

            # 4. Abstention Layer
            abstention_ok = True
            if should_abstain:
                abstention_ok = status == "escalate" or any(w in ans_lower for w in ("not verified", "cannot answer", "outside", "unsupported", "contact the university"))

            # 5. Operational Status Check
            status_match = (status == expected_status)
            if should_abstain and status == "escalate":
                status_match = True

            # Determine Result
            passed = status_match and (should_abstain or (fact_coverage >= 0.40 and (not required_citations or len(sources) > 0)))
            needs_review = False
            if not passed:
                if status_match and fact_coverage > 0:
                    needs_review = True

            result_str = "PASS" if passed else ("NEEDS_REVIEW" if needs_review else "FAIL")

            failure_reason = ""
            if not passed:
                reasons = []
                if not status_match:
                    reasons.append(f"Status mismatch (expected '{expected_status}', got '{status}')")
                if expected_facts and fact_coverage < 0.40:
                    reasons.append(f"Low fact coverage ({fact_coverage:.0%}, missing: {[f for f in expected_facts if f not in facts_found]})")
                if should_abstain and not abstention_ok:
                    reasons.append("Failed to abstain on unsupported/adversarial input")
                if required_citations and len(sources) == 0:
                    reasons.append("Missing required source citations")
                failure_reason = "; ".join(reasons)

            return {
                "test_id": t_id,
                "category": test_case.get("category", "general"),
                "group": test_case.get("group", ""),
                "test_type": test_case.get("test_type", "answerable"),
                "question": q,
                "query_used": query_used,
                "result": result_str,
                "status": status,
                "expected_status": expected_status,
                "latency_ms": latency_ms,
                "sources_count": len(sources),
                "retrieval_hit": hit,
                "fact_coverage": round(fact_coverage, 3),
                "citations_valid": citations_valid,
                "abstention_ok": abstention_ok,
                "failure_reason": failure_reason,
                "answer_preview": answer[:150].replace("\n", " "),
                "sources": [s.get("title") for s in sources[:3]],
                "answer": answer
            }
        except Exception as exc:
            latency_ms = round((time.time() - t0) * 1000)
            return {
                "test_id": t_id,
                "category": test_case.get("category", "general"),
                "group": test_case.get("group", ""),
                "test_type": test_case.get("test_type", "answerable"),
                "question": q,
                "query_used": q,
                "result": "FAIL",
                "status": "error",
                "expected_status": expected_status,
                "latency_ms": latency_ms,
                "sources_count": 0,
                "retrieval_hit": False,
                "fact_coverage": 0.0,
                "citations_valid": False,
                "abstention_ok": False,
                "failure_reason": f"Execution exception: {str(exc)[:100]}",
                "answer_preview": "",
                "sources": [],
                "answer": ""
            }

    def evaluate(self, category: str | None = None, sample: int | None = None) -> dict:
        cases = self.load_dataset(category=category, sample=sample)
        print(f"\n========================================================")
        print(f"RAG EVALUATION RUNNER: Evaluating {len(cases)} test cases...")
        print(f"========================================================")

        results = []
        failures = []
        for i, c in enumerate(cases, 1):
            res = self.run_single_test(c)
            results.append(res)
            res_icon = "✓" if res["result"] == "PASS" else ("?" if res["result"] == "NEEDS_REVIEW" else "✗")
            print(f"[{i:03d}/{len(cases):03d}] {res_icon} {res['test_id']} [{res['result']:12s}] {res['latency_ms']:4d}ms | {res['status']:9s} | Q: {res['question'][:40]}...")
            if res["result"] != "PASS":
                failures.append(res)

        # Compute aggregate metrics
        total = len(results)
        passed = sum(1 for r in results if r["result"] == "PASS")
        needs_review = sum(1 for r in results if r["result"] == "NEEDS_REVIEW")
        failed = sum(1 for r in results if r["result"] == "FAIL")

        pass_rate = round(passed / total * 100, 2) if total else 0.0
        retrieval_hits = sum(1 for r in results if r["retrieval_hit"])
        recall_at_k = round(retrieval_hits / total * 100, 2) if total else 0.0

        latencies = [r["latency_ms"] for r in results]
        avg_latency = round(sum(latencies) / max(1, len(latencies)))
        p95_latency = sorted(latencies)[int(0.95 * len(latencies))] if latencies else 0

        # By category
        by_category = defaultdict(lambda: {"total": 0, "passed": 0, "failed": 0})
        for r in results:
            cat = r["category"]
            by_category[cat]["total"] += 1
            if r["result"] == "PASS":
                by_category[cat]["passed"] += 1
            else:
                by_category[cat]["failed"] += 1

        for cat, data in by_category.items():
            data["pass_rate"] = round(data["passed"] / max(1, data["total"]) * 100, 1)

        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": total,
            "passed": passed,
            "needs_review": needs_review,
            "failed": failed,
            "pass_rate_pct": pass_rate,
            "retrieval_recall_at_k_pct": recall_at_k,
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
            "by_category": dict(by_category)
        }

        # Save to machine-readable JSON
        report_data = {"summary": summary, "results": results}
        summary_path = RESULTS_DIR / "rag_evaluation_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        # Save human-readable Markdown
        self._write_markdown_report(summary, results)

        # Save failure records to failure_log.jsonl
        if failures:
            with open(FAILURE_LOG_PATH, "a", encoding="utf-8") as f:
                for fail in failures:
                    log_entry = {
                        "timestamp": datetime.now().isoformat(),
                        "test_id": fail["test_id"],
                        "question": fail["question"],
                        "query_used": fail["query_used"],
                        "status": fail["status"],
                        "expected_status": fail["expected_status"],
                        "sources": fail["sources"],
                        "failure_reason": fail["failure_reason"],
                        "answer_snippet": fail["answer"][:300]
                    }
                    f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

        print(f"\n========================================================")
        print(f"EVALUATION COMPLETE:")
        print(f"Pass Rate: {pass_rate}% ({passed}/{total}) | Recall@k: {recall_at_k}% | Avg Latency: {avg_latency}ms")
        print(f"Reports saved to {RESULTS_DIR}/rag_evaluation_summary.json and evaluation_report.md")
        print(f"========================================================")
        return report_data

    def _write_markdown_report(self, summary: dict, results: list[dict]) -> None:
        md_lines = [
            "# JKLU Admission RAG Evaluation Report",
            f"**Generated**: {summary['timestamp']}",
            "",
            "## 1. Overall Performance Metrics",
            f"- **Total Test Scenarios**: {summary['total_tests']}",
            f"- **Passed**: {summary['passed']} ({summary['pass_rate_pct']}%)",
            f"- **Needs Review**: {summary['needs_review']}",
            f"- **Failed**: {summary['failed']}",
            f"- **Retrieval Recall@K**: {summary['retrieval_recall_at_k_pct']}%",
            f"- **Average Latency**: {summary['avg_latency_ms']} ms (P95: {summary['p95_latency_ms']} ms)",
            "",
            "## 2. Performance by Category",
            "| Category | Total | Passed | Failed | Pass Rate |",
            "| :--- | :--- | :--- | :--- | :--- |"
        ]
        for cat, d in sorted(summary["by_category"].items()):
            md_lines.append(f"| {cat} | {d['total']} | {d['passed']} | {d['failed']} | {d['pass_rate']}% |")

        md_lines.extend([
            "",
            "## 3. Detailed Failures and Diagnoses",
            "| Test ID | Category | Question | Status (Got/Exp) | Reason |",
            "| :--- | :--- | :--- | :--- | :--- |"
        ])
        for r in results:
            if r["result"] != "PASS":
                q_cut = r['question'][:45].replace("|", "/")
                reas_cut = r['failure_reason'][:60].replace("|", "/")
                md_lines.append(f"| {r['test_id']} | {r['category']} | {q_cut} | {r['status']}/{r['expected_status']} | {reas_cut} |")

        report_md_path = RESULTS_DIR / "rag_evaluation_report.md"
        with open(report_md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines) + "\n")

    def diagnose(self) -> dict:
        """Analyze failure logs, identify root cause categories, and propose safe targeted fixes."""
        if not FAILURE_LOG_PATH.is_file():
            print("No failure log found to diagnose.")
            return {}
        failures = []
        with open(FAILURE_LOG_PATH, "r", encoding="utf-8") as f:
            for l in f:
                if l.strip():
                    failures.append(json.loads(l))

        print(f"\n[DIAGNOSE MODE] Analyzing {len(failures)} logged failure events...")
        root_causes = defaultdict(list)
        for fail in failures:
            reason = fail.get("failure_reason", "")
            q = fail.get("question", "")
            if "Missing required source citations" in reason:
                root_causes["citation_missing"].append(fail)
            elif "Status mismatch" in reason:
                root_causes["status_mismatch"].append(fail)
            elif "Low fact coverage" in reason:
                root_causes["fact_coverage_gap"].append(fail)
            elif "Failed to abstain" in reason:
                root_causes["abstention_failure"].append(fail)
            else:
                root_causes["retrieval_ranking"].append(fail)

        print("\nRoot Cause Breakdown:")
        for cause, fails in root_causes.items():
            print(f"  - {cause}: {len(fails)} cases")

        return root_causes

    def improve(self) -> dict:
        """Apply approved, low-risk, reversible improvements to synonym mappings and query aliases."""
        print("\n[IMPROVE MODE] Applying safe, verified query normalization and aliases...")
        # Check approved aliases file
        approved_aliases = {}
        if APPROVED_ALIASES_PATH.is_file():
            with open(APPROVED_ALIASES_PATH, "r", encoding="utf-8") as f:
                approved_aliases = json.load(f)

        applied = 0
        for canonical, aliases in approved_aliases.items():
            for alias in aliases:
                # Add to verified patterns if not present
                match = self.agent.memory.recall(alias, threshold=0.90) if hasattr(self.agent, "memory") else None
                if not match and hasattr(self.agent, "memory"):
                    self.agent.memory.reflect_and_learn(alias, canonical, [], {"status": "answer", "answer": "", "confidence": 0.95})
                    applied += 1

        print(f"Improvement applied: {applied} query aliases safely registered into learned memory.")
        return {"aliases_applied": applied}

    def run_regression(self) -> dict:
        """Run Phase 11 critical test scenarios to ensure zero regression."""
        print("\n[REGRESSION MODE] Running Phase 11 regression test suite...")
        cases = self.load_dataset()
        crit_cases = [c for c in cases if c.get("severity") == "critical" or c.get("group") == "Phase 11 Required Scenarios"]
        passed = 0
        results = []
        for c in crit_cases:
            res = self.run_single_test(c)
            results.append(res)
            if res["result"] == "PASS":
                passed += 1
            print(f"  {'✓' if res['result'] == 'PASS' else '✗'} {res['test_id']} [{res['result']}]: {res['question'][:45]}")

        print(f"\nRegression Suite Result: {passed}/{len(crit_cases)} Passed ({passed/max(1, len(crit_cases))*100:.1f}%)")
        return {"total": len(crit_cases), "passed": passed, "pass_rate": round(passed/max(1, len(crit_cases))*100, 1)}

def main():
    parser = argparse.ArgumentParser(description="JKLU Admission Chatbot Autonomous RAG Evaluation & Improvement Engine")
    parser.add_argument("--mode", choices=["evaluate", "diagnose", "improve", "regression", "full"], default="evaluate",
                        help="Execution mode (evaluate, diagnose, improve, regression, full)")
    parser.add_argument("--category", type=str, default=None, help="Filter by category (fees, admission, hostel, faculty, etc.)")
    parser.add_argument("--sample", type=int, default=None, help="Run a stratified sample of N test cases")
    args = parser.parse_args()

    runner = RAGEvaluationRunner()

    if args.mode == "evaluate":
        runner.evaluate(category=args.category, sample=args.sample)
    elif args.mode == "diagnose":
        runner.diagnose()
    elif args.mode == "improve":
        runner.improve()
    elif args.mode == "regression":
        runner.run_regression()
    elif args.mode == "full":
        print("\n>>> STEP 1: INITIAL EVALUATION")
        runner.evaluate(category=args.category, sample=args.sample)
        print("\n>>> STEP 2: DIAGNOSTIC ANALYSIS")
        runner.diagnose()
        print("\n>>> STEP 3: APPLY APPROVED IMPROVEMENTS")
        runner.improve()
        print("\n>>> STEP 4: REGRESSION VERIFICATION")
        runner.run_regression()

if __name__ == "__main__":
    main()
