"""Latency & Memory Profiler for JKLU Admission Chatbot.

Runs 30 representative queries in cold and warm states across all pipeline stages,
measuring p50 and p95 per stage, end-to-end latency, and RSS memory.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import psutil

from jklu.agent import JKLUAgent
from jklu.utils import log

PROFILES = [
    # 1-4: Fees
    {"cat": "fees", "q": "What is the B.Tech CSE tuition fee?"},
    {"cat": "fees", "q": "What are the hostel and mess charges at JKLU?"},
    {"cat": "fees", "q": "What is the fee structure for MBA 2026?"},
    {"cat": "fees", "q": "Is there any caution deposit and is it refundable?"},
    # 5-7: Cut-offs & Eligibility
    {"cat": "cutoffs", "q": "What is the cutoff for B.Tech CSE admissions?"},
    {"cat": "cutoffs", "q": "What is the minimum eligibility criteria for B.Tech?"},
    {"cat": "cutoffs", "q": "What are the BCA admission eligibility and criteria?"},
    # 8-10: Placements
    {"cat": "placements", "q": "What is the highest and average package for B.Tech placements?"},
    {"cat": "placements", "q": "Which top companies visit JKLU for campus placements?"},
    {"cat": "placements", "q": "What are the placement statistics for M.Tech or MBA?"},
    # 11-13: Hostel
    {"cat": "hostel", "q": "What are the hostel room sharing options and air conditioning facilities?"},
    {"cat": "hostel", "q": "What are the hostel curfew timings and leave rules?"},
    {"cat": "hostel", "q": "Can first-year students stay outside campus or is hostel compulsory?"},
    # 14-17: Faculty
    {"cat": "faculty", "q": "Who is the Vice Chancellor of JKLU?"},
    {"cat": "faculty", "q": "Tell me about Dr. Amit Sinhal and his research area."},
    {"cat": "faculty", "q": "Who teaches machine learning and data science in the computer science department?"},
    {"cat": "faculty", "q": "Who is the Director of the Institute of Engineering and Technology?"},
    # 18-20: Scholarships
    {"cat": "scholarships", "q": "What scholarships are available based on Class 12 board marks?"},
    {"cat": "scholarships", "q": "Are there any merit scholarships for JEE Main percentile scorers?"},
    {"cat": "scholarships", "q": "Does JKLU offer sports scholarships or girl student fee concessions?"},
    # 21-23: Vague queries
    {"cat": "vague", "q": "Tell me about admissions."},
    {"cat": "vague", "q": "What courses are offered here?"},
    {"cat": "vague", "q": "Facilities in campus."},
    # 24-25: Follow-up queries (with history)
    {
        "cat": "follow_up",
        "q": "How do I apply for that?",
        "history": [
            {"role": "user", "content": "Tell me about B.Tech Computer Science."},
            {"role": "assistant", "content": "JKLU offers B.Tech in Computer Science and Engineering."}
        ]
    },
    {
        "cat": "follow_up",
        "q": "Are there any discounts or fee waivers on that?",
        "history": [
            {"role": "user", "content": "What is the B.Tech fee?"},
            {"role": "assistant", "content": "The B.Tech tuition fee is approximately Rs. 2,67,000 per year."}
        ]
    },
    # 26-28: Time-sensitive queries
    {"cat": "time_sensitive", "q": "What is the last date to apply for admission 2026?"},
    {"cat": "time_sensitive", "q": "When does the upcoming academic session 2026-27 start?"},
    {"cat": "time_sensitive", "q": "Are 2026 application deadlines announced?"},
    # 29-30: Unanswerable queries
    {"cat": "unanswerable", "q": "What will be the hostel fee in the year 2045?"},
    {"cat": "unanswerable", "q": "Does JKLU offer aerospace engineering with pilot license training?"},
]

def get_rss_mb() -> float:
    proc = psutil.Process(os.getpid())
    return round(proc.memory_info().rss / (1024 * 1024), 2)

def run_profiler(output_file: str | None = None) -> dict:
    print("=" * 80)
    print("JKLU Latency & Memory Profiler")
    print("=" * 80)
    
    rss_start = get_rss_mb()
    print(f"Initial Process RSS: {rss_start:.2f} MB")
    
    # 1. Cold agent initialization
    t_init_start = time.perf_counter()
    agent = JKLUAgent()
    init_ms = round((time.perf_counter() - t_init_start) * 1000, 2)
    rss_post_init = get_rss_mb()
    print(f"Agent Initialization: {init_ms:.1f} ms | Post-init RSS: {rss_post_init:.2f} MB")
    
    # 2. Cold query measurement (first query run on fresh agent)
    cold_item = PROFILES[0]
    print(f"\n[COLD RUN] Running first query without warmup: '{cold_item['q']}'...")
    res_cold = agent.ask(cold_item["q"])
    cold_e2e = res_cold.get("latency_ms", 0)
    cold_timings = res_cold.get("timings", {})
    print(f"Cold query latency: {cold_e2e} ms (Provider: {res_cold.get('provider')})")

    # 3. Warm run across all 30 queries
    print(f"\n[WARM RUN] Executing {len(PROFILES)} representative queries...")
    records = []
    
    for idx, item in enumerate(PROFILES, 1):
        q = item["q"]
        hist = item.get("history")
        cat = item.get("cat")
        
        t_start = time.perf_counter()
        res = agent.ask(q, history=hist)
        dur = (time.perf_counter() - t_start) * 1000
        
        t_dict = res.get("timings", {})
        rec = {
            "index": idx,
            "category": cat,
            "query": q,
            "status": res.get("status"),
            "provider": res.get("provider"),
            "tier_used": res.get("tier_used", "tier1_indexed"),
            "confidence": round(float(res.get("confidence", 0.0)), 3),
            "citations": len(res.get("sources", [])),
            "top_source": res.get("sources", [{}])[0].get("title", "") if res.get("sources") else "",
            "end_to_end_ms": round(dur, 2),
            "query_classification_ms": t_dict.get("query_classification_ms", 0.0),
            "memory_lookup_ms": t_dict.get("memory_lookup_ms", 0.0),
            "query_embedding_ms": t_dict.get("query_embedding_ms", 0.0),
            "faiss_search_ms": t_dict.get("faiss_search_ms", 0.0),
            "bm25_search_ms": t_dict.get("bm25_search_ms", 0.0),
            "rrf_fusion_ms": t_dict.get("rrf_fusion_ms", 0.0),
            "retrieval_total_ms": t_dict.get("retrieval_total_ms", 0.0),
            "live_fetch_total_ms": t_dict.get("live_fetch_total_ms", 0.0),
            "prompt_building_ms": t_dict.get("prompt_building_ms", 0.0),
            "llm_time_to_first_token_ms": t_dict.get("llm_time_to_first_token_ms", 0.0),
            "llm_total_ms": t_dict.get("llm_total_ms", 0.0),
            "post_processing_ms": t_dict.get("post_processing_ms", 0.0),
        }
        records.append(rec)
        print(f"  [{idx:02d}/30] ({cat[:8]:8s}) {dur:6.1f} ms | LLM={rec['llm_total_ms']:6.1f} ms | Ret={rec['retrieval_total_ms']:5.1f} ms | {q[:40]}...")

    rss_final = get_rss_mb()
    print(f"\nFinal Process RSS: {rss_final:.2f} MB")
    
    # Calculate statistics
    stages = [
        "query_classification_ms",
        "memory_lookup_ms",
        "query_embedding_ms",
        "faiss_search_ms",
        "bm25_search_ms",
        "rrf_fusion_ms",
        "retrieval_total_ms",
        "live_fetch_total_ms",
        "prompt_building_ms",
        "llm_time_to_first_token_ms",
        "llm_total_ms",
        "post_processing_ms",
        "end_to_end_ms",
    ]
    
    summary = {}
    for st in stages:
        vals = [r[st] for r in records]
        # For LLM metrics, also compute among non-zero calls
        non_zero_vals = [v for v in vals if v > 0]
        summary[st] = {
            "p50": round(float(np.percentile(vals, 50)), 2),
            "p95": round(float(np.percentile(vals, 95)), 2),
            "mean": round(float(np.mean(vals)), 2),
            "max": round(float(np.max(vals)), 2),
            "p50_active": round(float(np.percentile(non_zero_vals, 50)), 2) if non_zero_vals else 0.0,
            "p95_active": round(float(np.percentile(non_zero_vals, 95)), 2) if non_zero_vals else 0.0,
        }

    # Print Table
    print("\n" + "=" * 80)
    print("STAGE-BY-STAGE LATENCY SUMMARY (Warm, N=30)")
    print("=" * 80)
    print(f"{'Pipeline Stage':<30} | {'p50 (ms)':>10} | {'p95 (ms)':>10} | {'Mean (ms)':>10} | {'Max (ms)':>10}")
    print("-" * 80)
    for st in stages:
        s = summary[st]
        print(f"{st:<30} | {s['p50']:10.1f} | {s['p95']:10.1f} | {s['mean']:10.1f} | {s['max']:10.1f}")
    print("-" * 80)
    print(f"{'Process RSS Memory':<30} | {'Initial':>10} | {'Post-Init':>10} | {'Final':>10} | {'Cap':>10}")
    print(f"{'':<30} | {rss_start:8.1f}MB | {rss_post_init:8.1f}MB | {rss_final:8.1f}MB | {'450.0 MB':>10}")
    print("=" * 80)
    
    output_data = {
        "timestamp": time.time(),
        "rss_initial_mb": rss_start,
        "rss_post_init_mb": rss_post_init,
        "rss_final_mb": rss_final,
        "cold_query_ms": cold_e2e,
        "cold_timings": cold_timings,
        "summary": summary,
        "queries": records,
    }
    
    if output_file:
        out_p = Path(output_file)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)
        print(f"\nDetailed profile saved to: {out_p}")
        
    return output_data

if __name__ == "__main__":
    out_path = ROOT / "data" / "profile_before.json"
    if len(sys.argv) > 1:
        out_path = Path(sys.argv[1])
    run_profiler(str(out_path))

