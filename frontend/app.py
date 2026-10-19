"""Streamlit chat UI.  Talks to the FastAPI backend when it is running, otherwise
loads the agent in-process, so it works both from `python run.py` and standalone:

    streamlit run frontend/app.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

API_URL = os.environ.get("JKLU_API_URL", "http://127.0.0.1:8000")
CATEGORIES = ["admission", "academics", "hostel", "fees", "examination", "scholarships", "contact",
              "notices", "general"]
SAMPLES = [
    "What is the eligibility for B.Tech admission?",
    "What is the tuition fee for B.Tech in 2026-27?",
    "What scholarship can I get with JEE Main percentile above 95?",
    "What are the hostel rules for visitors?",
    "Which letter grades are awarded at JKLU?",
    "How can I contact the admissions office?",
]
BADGE = {"answer": ("Answer", "green"), "clarify": ("Needs clarification", "orange"),
         "escalate": ("Please contact the university", "red"), "smalltalk": ("", "gray")}

st.set_page_config(page_title="JKLU Information Assistant", page_icon="🎓", layout="centered")


@st.cache_resource(show_spinner="Loading the JKLU knowledge base ...")
def local_agent():
    from jklu.agent import JKLUAgent
    from jklu.index import ensure_index
    ensure_index()
    return JKLUAgent()


def api_up() -> bool:
    try:
        import requests
        return requests.get(f"{API_URL}/health", timeout=2).json().get("status") == "ok"
    except Exception:
        return False


def ask(question, category, top_k, history):
    payload = {"question": question, "category": category, "top_k": top_k, "history": history}
    if api_up():
        import requests
        r = requests.post(f"{API_URL}/chat", json=payload, timeout=180)
        r.raise_for_status()
        return r.json()
    return local_agent().ask(question, category=category, top_k=top_k, history=history)


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("🎓 JKLU Assistant")
    st.caption("Answers come only from JKLU's official website and documents.")
    cat = st.selectbox("Limit to topic", ["All topics"] + CATEGORIES)
    top_k = st.slider("Passages to retrieve", 3, 8, 5)
    st.markdown("**Try asking**")
    for i, s in enumerate(SAMPLES):
        if st.button(s, key=f"s{i}", use_container_width=True):
            st.session_state["pending"] = s
    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state["messages"] = []
        st.rerun()

st.title("JKLU University Information Assistant")
st.caption("Admissions • Fees • Scholarships • Hostel • Examinations • Programmes • Contacts")

if "messages" not in st.session_state:
    st.session_state["messages"] = []


def render(msg):
    st.markdown(msg["content"])
    meta = msg.get("meta")
    if not meta:
        return
    label, color = BADGE.get(meta["status"], ("", "gray"))
    if label:
        st.markdown(f":{color}[**{label}**] · confidence {meta.get('confidence', 0):.0%}")
    if meta.get("sources"):
        with st.expander(f"Sources ({len(meta['sources'])})"):
            for s in meta["sources"]:
                page = f" · p.{s['page']}" if s.get("page") else ""
                year = f" · {s['academic_year']}" if s.get("academic_year") else ""
                st.markdown(f"**[{s['n']}] [{s['title']}]({s['url']})** — {s['category']}{page}{year}")
                st.caption(s["snippet"])
    with st.expander("Why this response?"):
        st.write(meta.get("reason", ""))
        st.caption(f"{meta.get('latency_ms', 0)} ms · {meta.get('provider') or 'no LLM'}")


for m in st.session_state["messages"]:
    with st.chat_message(m["role"]):
        render(m)

typed = st.chat_input("Ask about JKLU admissions, fees, hostel, exams ...")
question = typed or st.session_state.pop("pending", None)

if question:
    history = [{"role": m["role"], "content": m["content"]} for m in st.session_state["messages"][-8:]]
    st.session_state["messages"].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        try:
            with st.spinner("Searching JKLU documents ..."):
                res = ask(question, None if cat == "All topics" else cat, top_k, history)
            msg = {"role": "assistant", "content": res["answer"], "meta": res}
        except Exception as exc:
            msg = {"role": "assistant", "content": f"Sorry, something went wrong: {exc}"}
        render(msg)
    st.session_state["messages"].append(msg)
