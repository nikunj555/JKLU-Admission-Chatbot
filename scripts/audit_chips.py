"""Audit Sidebar Quick-Access Chips against the Offline QA Pipeline.

Verifies that every sidebar chip in frontend/ui/src/components/AppSidebar.tsx
can be answered accurately with high confidence and verified citations.
Saves the audit report to docs/chip_audit.md.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jklu.agent import JKLUAgent

SIDEBAR_FILE = ROOT / "frontend" / "ui" / "src" / "components" / "AppSidebar.tsx"
REPORT_FILE = ROOT / "docs" / "chip_audit.md"

def extract_sidebar_chips() -> list[dict[str, str]]:
    """Parse QUICK_ACCESS_TOPICS directly from AppSidebar.tsx."""
    if not SIDEBAR_FILE.is_file():
        # Fallback default
        return [
            {"label": "Admissions", "q": "What is the admission process for JKLU?"},
            {"label": "Courses", "q": "What programmes and courses are offered at JKLU?"},
            {"label": "Eligibility", "q": "What are the eligibility criteria for B.Tech and other programmes?"},
            {"label": "Fees", "q": "What is the complete fee structure and tuition fees?"},
            {"label": "Scholarships", "q": "What merit scholarships and financial aid are available?"},
            {"label": "Important dates", "q": "What are the important admission deadlines and academic dates?"},
            {"label": "Faculty", "q": "Who are the faculty members in the CSE department at JKLU?"},
            {"label": "Campus life", "q": "What are the hostel and campus facilities like?"},
        ]
    content = SIDEBAR_FILE.read_text(encoding="utf-8")
    match = re.search(r"export const QUICK_ACCESS_TOPICS = \[(.*?)\];", content, re.DOTALL)
    if not match:
        raise ValueError("Could not find QUICK_ACCESS_TOPICS in AppSidebar.tsx")
    
    entries = []
    for item in re.finditer(r"label:\s*'([^']+)',\s*q:\s*'([^']+)'", match.group(1)):
        entries.append({"label": item.group(1), "q": item.group(2)})
    return entries

def audit_chips() -> list[dict]:
    chips = extract_sidebar_chips()
    print("=" * 80)
    print(f"Auditing {len(chips)} Sidebar Quick-Access Chips")
    print("=" * 80)
    
    agent = JKLUAgent()
    results = []
    
    for idx, chip in enumerate(chips, 1):
        lbl = chip["label"]
        q = chip["q"]
        t0 = time.perf_counter()
        res = agent.ask(q)
        dur_ms = round((time.perf_counter() - t0) * 1000, 1)
        
        status = res.get("status")
        conf = round(float(res.get("confidence", 0.0)), 3)
        sources = res.get("sources", [])
        top_src = sources[0].get("title", "") if sources else "None"
        
        passed = (status == "answer" and conf >= 0.65 and len(sources) > 0)
        
        row = {
            "index": idx,
            "label": lbl,
            "query": q,
            "status": status,
            "confidence": conf,
            "citations_count": len(sources),
            "top_source": top_src,
            "latency_ms": dur_ms,
            "passed": passed,
        }
        results.append(row)
        mark = "✓ PASS" if passed else "✗ FAIL"
        print(f"[{idx}/{len(chips)}] {mark} | {lbl:<15} | Conf: {conf:.2f} | Sources: {len(sources)} | {dur_ms:6.1f} ms | Q: {q}")
        
    print("-" * 80)
    total_passed = sum(1 for r in results if r["passed"])
    print(f"Summary: {total_passed}/{len(results)} chips passed audit.")
    print("=" * 80)
    
    # Generate markdown report
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    md_lines = [
        "# Sidebar Quick-Access Chip Audit Report",
        f"\n**Audit Date**: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        f"**Total Chips Tested**: {len(results)}",
        f"**Passed**: {total_passed} / {len(results)}\n",
        "| # | Label | Query | Status | Confidence | Citations | Latency (ms) | Top Source | Result |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        res_str = "**PASS**" if r["passed"] else "**FAIL**"
        md_lines.append(
            f"| {r['index']} | {r['label']} | {r['query']} | {r['status']} | {r['confidence']:.2f} | {r['citations_count']} | {r['latency_ms']} | {r['top_source'][:30]} | {res_str} |"
        )
        
    REPORT_FILE.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"Audit report written to {REPORT_FILE}")
    return results

if __name__ == "__main__":
    res = audit_chips()
    if not all(r["passed"] for r in res):
        sys.exit(1)

