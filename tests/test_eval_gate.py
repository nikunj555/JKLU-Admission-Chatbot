"""Regression evaluation gate for JKLU Assistant.

Verifies:
1. Retrieval Hit@1 >= 70%
2. Unanswerable Refusal Rate >= 80%
3. End-to-end Latency p50 < 1,000 ms
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from jklu.agent import JKLUAgent
from scripts.eval import check_source_hit
GOLD_PATH = ROOT / "data" / "eval" / "gold.jsonl"
EVAL_AFTER_PATH = ROOT / "docs" / "eval_after.md"


def test_eval_gate_metrics_from_report():
    """Verify the certified evaluation report (docs/eval_after.md) passes all gates."""
    assert EVAL_AFTER_PATH.exists(), f"Evaluation report not found at {EVAL_AFTER_PATH}"
    content = EVAL_AFTER_PATH.read_text(encoding="utf-8")

    # 1. Retrieval Hit@1 >= 70%
    m_hit = re.search(r"\|\s*\*\*Retrieval Hit@1\*\*\s*\|\s*[^|]+\|\s*\*\*([0-9.]+)%\*\*", content)
    assert m_hit is not None, "Retrieval Hit@1 not found in report"
    hit1 = float(m_hit.group(1))
    assert hit1 >= 70.0, f"Hit@1 {hit1}% is below required 70.0% threshold"

    # 2. Unanswerable Refusal Rate >= 80%
    m_refusal = re.search(r"\|\s*\*\*Unanswerable Refusal Rate\*\*\s*\|\s*[^|]+\|\s*\*\*([0-9.]+)%\*\*", content)
    assert m_refusal is not None, "Unanswerable Refusal Rate not found in report"
    refusal_rate = float(m_refusal.group(1))
    assert refusal_rate >= 80.0, f"Refusal rate {refusal_rate}% is below required 80.0% threshold"

    # 3. End-to-End Latency p50 < 1000 ms
    m_lat = re.search(r"\|\s*\*\*End-to-End Latency\*\*\s*\|\s*\*\*([0-9.]+)\*\*", content)
    assert m_lat is not None, "End-to-End Latency p50 not found in report"
    p50_lat = float(m_lat.group(1))
    assert p50_lat < 1000.0, f"Latency p50 {p50_lat}ms exceeds 1,000ms threshold"


def test_eval_gate_unanswerable_refusal_live():
    """Dynamically verify unanswerable / out-of-scope questions refuse at >= 80%."""
    assert GOLD_PATH.exists(), f"Gold set not found at {GOLD_PATH}"
    lines = [json.loads(line) for line in GOLD_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    unanswerable = [row for row in lines if not row.get("answerable", True)]
    assert len(unanswerable) >= 10, "Expected at least 10 unanswerable test queries"

    agent = JKLUAgent()
    refusals = 0
    for row in unanswerable:
        res = agent.ask(row["question"])
        if res.get("status") == "escalate":
            refusals += 1

    rate = (refusals / len(unanswerable)) * 100
    assert rate >= 80.0, f"Live unanswerable refusal rate was {rate}%, expected >= 80%"
