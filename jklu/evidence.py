"""Evidence / confidence check: decide ANSWER, CLARIFY or ESCALATE.

A raw similarity score is not enough (a high score does not guarantee the
answer is in the text, and "fee in 2030" is *semantically* close to the fee
page).  The decision combines several independent signals:

  1. ambiguity       - a bare generic question ("what is the fee?")         -> clarify
  2. year support    - a year/session in the question absent from evidence  -> escalate
  3. coverage        - IDF-weighted share of the question's content words
                       found in the top retrieved passages (+ synonyms)
  4. dense cosine    - semantic similarity (only with a real embedding model)
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field

from . import config as C
from . import textproc as T

ANSWER, CLARIFY, ESCALATE = "answer", "clarify", "escalate"

_GENERIC_STEMS = T.GENERIC_HEAD_STEMS
_YEAR = re.compile(r"\b(20[0-4]\d)\b")

CLARIFY_OPTIONS = {
    "fee": "Which fee do you mean - tuition/academic fee, technology fee, hostel & mess fee, transport, "
           "or the refund policy? And for which programme (B.Tech, B.Des, BBA, M.Tech, M.Des, PhD)?",
    "hostel": "What would you like to know about the hostel - hostel rules and timings, room allotment, "
              "visitors, fees, or the warden's contact?",
    "admission": "What do you want to know about admissions - eligibility, the application process, "
                 "required documents, entrance exams, or fees? And for which programme?",
    "eligibility": "Eligibility for which programme - B.Tech, B.Des, BBA, M.Tech, M.Des or PhD?",
    "scholarship": "Which programme are you asking about (B.Tech, B.Des, BBA, M.Tech ...) and on what basis "
                   "(Class XII marks, JEE Main, CUET, JKLU-DET, GATE, sibling/alumni ...)?",
    "deadline": "Deadline for what - application, fee payment, withdrawal/refund, or an academic-calendar event?",
    "date": "Which date do you mean - application, entrance exam, fee payment, or an academic-calendar event?",
    "exam": "What about exams - examination rules, grading, attendance, backlog/re-exam, or the schedule?",
    "examination": "What about examinations - rules, grading, attendance, re-examination, or the schedule?",
    "contact": "Which office do you need - Admissions, Registrar, Placements, Hostel warden, or another?",
    "faculty": "Which department or institute are you looking for - Engineering & Technology, Design, or Management? Or are you looking for a specific professor?",
    "notice": "Which kind of notice are you looking for - admissions, examination, hostel, or general?",
    "program": "Which programme are you interested in - B.Tech, B.Des, BBA, M.Tech, M.Des or PhD?",
    "course": "Which programme are you interested in - B.Tech, B.Des, BBA, M.Tech, M.Des or PhD?",
}
def _chips(*pairs):
    return [{"label": a, "question": b} for a, b in pairs]


PROGRAMMES = ("B.Tech", "B.Des", "BBA", "M.Tech", "M.Des", "PhD")
CLARIFY_CHIPS = {
    "fee": _chips(("Tuition fee", "What is the annual tuition fee for B.Tech?"),
                  ("Hostel and mess fee", "What is the hostel and mess fee?"),
                  ("Transport fee", "What is the transport fee?"),
                  ("Refund policy", "What is the fee refund policy?")),
    "hostel": _chips(("Hostel rules", "What are the hostel rules?"),
                     ("Visitor rules", "What are the hostel rules for visitors?"),
                     ("Entry and exit timings", "What are the hostel entry and exit timings?"),
                     ("Hostel fee", "What is the hostel fee?")),
    "admission": _chips(("Eligibility", "What is the eligibility for B.Tech admission?"),
                        ("Application process", "What are the steps in the application process?"),
                        ("Required documents", "Which documents are required for admission?"),
                        ("Entrance exams", "Which entrance exams does JKLU accept?")),
    "eligibility": _chips(*[(p, f"What is the eligibility for {p} admission?") for p in PROGRAMMES]),
    "scholarship": _chips(("JEE Main based", "What scholarship can I get with JEE Main percentile?"),
                          ("Class XII marks based", "What scholarship is available based on Class XII marks?"),
                          ("CUET / JKLU-DET based", "What scholarships are available for CUET or JKLU-DET?"),
                          ("GATE (M.Tech)", "What scholarship is available for GATE qualified M.Tech students?")),
    "deadline": _chips(("Application", "What is the application deadline?"),
                       ("Fee payment", "What is the fee payment deadline?"),
                       ("Academic calendar", "Where can I see the academic calendar?")),
    "exam": _chips(("Grading", "Which letter grades are awarded at JKLU?"),
                   ("Attendance rules", "What are the rules on student attendance?"),
                   ("Academic probation", "When is a student placed on academic probation?"),
                   ("Unfair means", "What is the penalty for using unfair means in examinations?")),
    "contact": _chips(("Admissions office", "How can I contact the admissions office?"),
                      ("Registrar", "What is the phone number of the Registrar?"),
                      ("Campus location", "Where is the JKLU campus located?")),
    "faculty": _chips(("Engineering Faculty", "Tell me about the engineering faculty"),
                      ("Design Faculty", "Tell me about the design faculty"),
                      ("Management Faculty", "Tell me about the management faculty")),
    "program": _chips(*[(p, f"What does the {p} programme offer?") for p in PROGRAMMES]),
}
CLARIFY_CHIPS["examination"] = CLARIFY_CHIPS["exam"]
CLARIFY_CHIPS["course"] = CLARIFY_CHIPS["program"]
CLARIFY_CHIPS["date"] = CLARIFY_CHIPS["deadline"]

DEFAULT_CLARIFY = ("Could you be a little more specific? For example, mention the programme (B.Tech, B.Des, "
                   "BBA, ...) and what you want to know - eligibility, fees, hostel, scholarships, exams, etc.")


@dataclass
class Evidence:
    status: str
    sufficient: bool
    confidence: float
    reason: str
    coverage: float = 0.0
    dense_best: float | None = None
    clarification: str | None = None
    missing_terms: list[str] = field(default_factory=list)
    suggestions: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def _evidence_tokens(passages: list[dict], n: int) -> set[str]:
    toks: set[str] = set()
    for p in passages[:n]:
        toks.update(T.tokens(f"{p.get('title', '')} {p.get('section', '')} {p.get('text', '')}"))
    return toks


def _idf(term: str, kb) -> float:
    bm = getattr(kb, "bm25", None)
    if bm is None:
        return 1.0
    if term in bm.idf:
        return bm.idf[term]
    return min(2.5, math.log(1.0 + (bm.n + 0.5) / 0.5))          # capped weight for unseen terms


def check(question: str, search_out: dict, kb=None) -> Evidence:
    """Judge whether `search_out['results']` can support an answer to `question`."""
    results = search_out.get("results", [])
    terms = search_out.get("terms") or T.content_terms(question)
    semantic = bool(search_out.get("semantic"))

    # ---- 1. nothing to judge / too vague -----------------------------------------
    if not terms:
        return Evidence(CLARIFY, False, 0.0, "The question contains no searchable content words.",
                        clarification=DEFAULT_CLARIFY)
    if len(terms) == 1 and terms[0] in _GENERIC_STEMS:
        head = terms[0]
        key = next((k for k in CLARIFY_OPTIONS if T.stem(k) == head), None)
        return Evidence(CLARIFY, False, 0.3, f"The question is too general ('{head}').",
                        clarification=CLARIFY_OPTIONS.get(key, DEFAULT_CLARIFY),
                        suggestions=CLARIFY_CHIPS.get(key, []))

    # ---- 1b. Intent: Irrelevant vs Academic Concept -----------------------------
    intent = T.classify_query_intent(question)
    if intent == T.INTENT_IRRELEVANT:
        return Evidence(ESCALATE, False, 0.0, "The question is off-topic and unrelated to university information or academic studies.")
    if intent == T.INTENT_ACADEMIC:
        return Evidence(ANSWER, True, 0.95, "General academic/technical concept query suitable for AI tutor explanation.",
                        coverage=1.0, dense_best=0.85)

    if not results:
        return Evidence(ESCALATE, False, 0.0, "No passages were retrieved.")

    top_n = 5
    ev_tokens = _evidence_tokens(results, top_n)
    ev_text = " ".join(p.get("text", "") for p in results[:5]).lower()

    # ---- 2. year support -----------------------------------------------------------
    years = set(_YEAR.findall(question))
    unsupported = [y for y in years if y not in ev_text]
    if unsupported:
        return Evidence(
            ESCALATE, False, 0.15,
            f"The question refers to {', '.join(sorted(unsupported))}, which does not appear in the retrieved "
            "JKLU documents, so any answer would be a guess.",
            missing_terms=sorted(unsupported))

    # ---- 3. IDF-weighted coverage --------------------------------------------------
    num = den = 0.0
    missing: list[str] = []
    for t in terms:
        w = _idf(t, kb)
        den += w
        if t in ev_tokens or any(s in ev_tokens for s in T.synonym_stems(t)):
            num += w
        else:
            missing.append(t)
    coverage = num / den if den else 0.0

    # ---- 4. dense similarity (semantic model only) --------------------------------
    dense_best = None
    if semantic:
        ds = [p["dense_score"] for p in results[:top_n] if p.get("dense_score") is not None]
        dense_best = max(ds) if ds else 0.0

    # Core non-auxiliary missing terms (ignore pure numbers, temporal markers, and qualifiers)
    non_aux_missing = [m for m in missing if not (m.isdigit() or m in ("year", "semest", "total", "full", "all", "durat", "cours", "entir"))]

    if semantic:
        d_norm = min(1.0, max(0.0, ((dense_best or 0.0) - 0.15) / 0.5))
        confidence = 0.6 * coverage + 0.4 * d_norm
        strong = (dense_best or 0) >= 0.50 and (coverage >= 0.25 or not non_aux_missing)
        ok = (coverage >= C.MIN_COVERAGE and (dense_best or 0) >= C.MIN_DENSE_SCORE) or strong or coverage >= 0.85 or (not non_aux_missing and (dense_best or 0) >= C.MIN_DENSE_SCORE)
        partial = coverage >= C.CLARIFY_COVERAGE and (dense_best or 0) >= 0.8 * C.MIN_DENSE_SCORE
    else:
        confidence = coverage
        ok = coverage >= C.MIN_COVERAGE or not non_aux_missing
        partial = coverage >= C.CLARIFY_COVERAGE

    # Questions that mention no JKLU topic at all ("capital of France") must clear a much higher bar,
    # otherwise generic words ("best", "world", "team") that occur somewhere in the corpus fake relevance.
    on_topic = bool(search_out.get("routed"))
    if not on_topic:
        ok = ok and coverage >= (0.7 if semantic else 0.85) and (not semantic or (dense_best or 0) >= 0.45)
        partial = False

    det = f"coverage={coverage:.2f}" + (f", best cosine={dense_best:.2f}" if dense_best is not None else "")
    if ok:
        return Evidence(ANSWER, True, round(min(confidence, 0.99), 3), f"Relevant evidence found ({det}).",
                        coverage, dense_best, missing_terms=missing)
    if partial:
        titles = ", ".join(dict.fromkeys(p.get("title", "") for p in results[:3] if p.get("title")))
        miss = ", ".join(missing[:4]) if missing else "the specific detail"
        return Evidence(
            CLARIFY, False, round(confidence, 3), f"Evidence only partly matches the question ({det}).",
            coverage, dense_best,
            clarification=(f"I found related material ({titles}) but nothing that clearly covers "
                           f"\"{miss}\". Could you rephrase or add detail such as the programme or year?"),
            missing_terms=missing)
    return Evidence(ESCALATE, False, round(confidence, 3), f"Retrieved evidence is weak ({det}).",
                    coverage, dense_best, missing_terms=missing)
