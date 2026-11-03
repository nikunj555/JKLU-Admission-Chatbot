import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jklu.agent import JKLUAgent

agent = JKLUAgent()

test_queries = [
    ("CSE", "who are the CSE faculty?"),
    ("B.Tech", "list all b.tech faculty"),
    ("BBA", "bba faculty"),
    ("B.Des", "b.des faculty"),
    ("MBA", "mba professors"),
    ("ECE", "who teaches in ece?"),
    ("Named Person", "tell me about Dr. Amit Sinhal"),
    ("Unknown Dept", "who are the aerospace faculty?"),
    ("Plain Faculty", "faculty"),
    ("Follow-up", "show remaining faculty"),
]

print("=" * 80)
print("10 Sample Faculty Queries Execution")
print("=" * 80)

for label, q in test_queries:
    t0 = time.perf_counter()
    history = [
        {"role": "user", "content": "who are the cse faculty?"},
        {"role": "assistant", "content": "Here is CSE faculty roster with 20 members."}
    ] if label == "Follow-up" else None
    
    res = agent.ask(q, history=history)
    dur = round((time.perf_counter() - t0) * 1000, 1)
    
    status = res.get("status")
    srcs = len(res.get("sources", []))
    prov = res.get("provider")
    ans_snippet = res.get("answer", "").replace("\n", " ")[:160]
    
    print(f"[{label:14s}] {dur:6.1f} ms | Status: {status:8s} | Sources: {srcs:2d} | Provider: {prov or 'none':13s}")
    print(f"   Q: {q}")
    print(f"   Ans: {ans_snippet}...")
    if res.get("suggestions"):
        print(f"   Suggestions: {res['suggestions']}")
    print("-" * 80)
