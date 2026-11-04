#!/usr/bin/env python3
"""Diagnose quality failures from gold.jsonl across the 8-category taxonomy."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jklu.agent import JKLUAgent
from jklu.utils import read_jsonl

rows = read_jsonl(ROOT / "data" / "eval" / "gold.jsonl")
agent = JKLUAgent()

failures = []
for r in rows:
    q = r["question"]
    is_ans = r.get("answerable", True)
    exp_facts = r.get("expected_facts", [])
    exp_source = r.get("expected_source", "")
    history = r.get("history")
    res = agent.ask(q, history=history)
    ans = res.get("answer", "")
    sources = res.get("sources", [])
    status = res.get("status", "answer")
    ans_clean = ans.lower()
    found_facts = [f for f in exp_facts if f.lower() in ans_clean or f.lower().replace(",", "") in ans_clean.replace(",", "")]
    if not is_ans:
        if status == "answer" and "could not be verified" not in ans_clean and "escalat" not in ans_clean:
            failures.append(("h_unanswerable_missing_data", r["id"], q, ["Proper refusal / escalation"], ans[:120], [s.get("title") for s in sources[:2]]))
    else:
        if len(found_facts) < max(1, len(exp_facts) // 2):
            source_titles = [(s.get("title") or "") for s in sources]
            source_text = " ".join((s.get("snippet") or s.get("text") or "") for s in sources).lower()
            missing = [f for f in exp_facts if f not in found_facts]
            if history and any(k in q.lower() for k in ("it", "this", "fee", "cost", "eligib")) and len(q.split()) <= 6:
                failures.append(("f_followup_resolution_failed", r["id"], q, missing, ans[:120], source_titles[:2]))
            elif any(f.lower() in source_text for f in missing):
                failures.append(("e_llm_dropped_or_hallucinated", r["id"], q, missing, ans[:120], source_titles[:2]))
            elif any(exp_source.lower() in st.lower() for st in source_titles):
                failures.append(("c_chunk_cut_off", r["id"], q, missing, ans[:120], source_titles[:2]))
            else:
                failures.append(("a_chunk_never_retrieved", r["id"], q, missing, ans[:120], source_titles[:2]))

report_lines = [
    "# JKLU Assistant - Quality Diagnosis & Failure Taxonomy",
    "",
    f"**Total Evaluated Questions**: {len(rows)}",
    f"**Total Failing Queries**: {len(failures)}",
    "",
    "## 1. Summary Counts by Root-Cause Category",
    "",
    "| Category | Code | Failure Count | Description |",
    "| :--- | :---: | :---: | :--- |",
]

codes = [
    ("a_chunk_never_retrieved", "(a)", "Chunk never retrieved (sparse/dense miss or term mismatch)"),
    ("b_chunk_ranked_too_low", "(b)", "Chunk retrieved but ranked outside top-k"),
    ("c_chunk_cut_off", "(c)", "Chunk retrieved but fact truncated/cut off"),
    ("d_router_mismatch", "(d)", "Query router picked wrong category filter"),
    ("e_llm_dropped_or_hallucinated", "(e)", "LLM prompt had facts in context but dropped or hallucinated them"),
    ("f_followup_resolution_failed", "(f)", "Follow-up question resolution failed (missed prior conversational turn)"),
    ("g_learning_memory_mismatch", "(g)", "Learning memory returned poisoned/outdated answer"),
    ("h_unanswerable_missing_data", "(h)", "Unanswerable query answered with false claims instead of escalating"),
]

for cat_key, code, desc in codes:
    items = [f for f in failures if f[0] == cat_key]
    report_lines.append(f"| **{desc}** | `{code}` | **{len(items)}** | {cat_key} |")

report_lines.append("")
report_lines.append("## 2. In-Depth Failure Analysis with Concrete Examples")
report_lines.append("")

for cat_key, code, desc in codes:
    items = [f for f in failures if f[0] == cat_key]
    report_lines.append(f"### {code} {desc} (Count: {len(items)})")
    if not items:
        report_lines.append("_No failures recorded in this category._\n")
        continue
    for it in items[:3]:
        report_lines.append(f"- **Query [ID {it[1]}]**: `\"{it[2]}\"`")
        report_lines.append(f"  - **Expected Fact(s)**: `{it[3]}`")
        report_lines.append(f"  - **Retrieved Chunks / Sources**: `{it[5]}`")
        report_lines.append(f"  - **Actual Bot Answer**: `\"{it[4]}...\"`")
    report_lines.append("")

out_file = ROOT / "docs" / "quality_diagnosis.md"
out_file.write_text("\n".join(report_lines), encoding="utf-8")
print(f"Written diagnosis to {out_file}")

