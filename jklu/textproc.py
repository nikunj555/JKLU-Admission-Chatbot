"""Query/document text processing shared by BM25, evidence checking and routing."""
from __future__ import annotations

import difflib
import re
from functools import lru_cache

STOPWORDS = frozenset("""
a about above after again against all also am an and any are as at be because been before being below between
both but by can could did do does doing down during each few for from further had has have having he her here
hers him his how i if in into is it its itself just me more most my no nor not now of off on once only or other
our out over own same she should so some such than that the their them then there these they this those through
to too under until up very was we were what when where which while who whom why will with would you your yours
tell give please know want need like get got let us may might shall kindly information info details detail
regarding provide explain describe list show say said ask asking question answer jklu jk lakshmipat university
understand understanding help find finding look looking looks available possible
anyone someone everything anything
college student students s t whats hows
""".split())

# spelling variants / compounds normalised before tokenising
_NORMALISE = [
    (re.compile(r"\bbachelors? of technology\b|\bb\.?\s?e\.?\s?/\s?b\.?\s?tech\b", re.I), "btech"),
    (re.compile(r"\bmasters? of technology\b", re.I), "mtech"),
    (re.compile(r"\bbachelors? of design\b", re.I), "bdes"),
    (re.compile(r"\bmasters? of design\b", re.I), "mdes"),
    (re.compile(r"\bbachelors? of business administration\b", re.I), "bba"),
    (re.compile(r"\bdoctor(ate)? of philosophy\b", re.I), "phd"),
    (re.compile(r"\bph\.?\s?d\b\.?", re.I), "phd"),
    (re.compile(r"\b([bm])\.\s?(tech|des|sc|com|a|ed)\b\.?", re.I), r"\1\2"),
    (re.compile(r"\bb\.?b\.?a\b\.?", re.I), "bba"),
    (re.compile(r"\bprogrammes?\b", re.I), "program"),
    (re.compile(r"\bcalander\b", re.I), "calendar"),
    (re.compile(r"\bcentre(s)?\b", re.I), r"center\1"),
    (re.compile(r"\bcgpa\b|\bsgpa\b|\bgpa\b", re.I), "grade point"),
    (re.compile(r"\bhostellers?\b|\bhostelites?\b", re.I), "hostel student"),
    (re.compile(r"\be-?mail\b", re.I), "email"),
    # Temporal, duration & semester phrases
    (re.compile(r"\b(\d+)\s*(?:years?|yrs?|yr)\b", re.I), r"\1 year"),
    (re.compile(r"\b(\d+)\s*(?:sems?|semesters?)\b", re.I), r"\1 semester"),
    (re.compile(r"\b(\d+)\s*(?:months?|mos?)\b", re.I), r"\1 month"),
    (re.compile(r"\b(\d+)\s*(?:lakhs?|lac|lacs|lpa)\b", re.I), r"\1 lakh"),
    (re.compile(r"\b(\d+)\s*(?:percent|%)\b", re.I), r"\1 percent"),
    (re.compile(r"\b(1st|first)\s*year\b", re.I), "1 year"),
    (re.compile(r"\b(2nd|second)\s*year\b", re.I), "2 year"),
    (re.compile(r"\b(3rd|third)\s*year\b", re.I), "3 year"),
    (re.compile(r"\b(4th|fourth)\s*year\b", re.I), "4 year"),
    (re.compile(r"\b(10th|tenth|class\s*10|class\s*x)\b", re.I), "class 10"),
    (re.compile(r"\b(12th|twelfth|class\s*12|class\s*xii)\b", re.I), "class 12"),
    # Indian English / common short forms
    (re.compile(r"\bfee[-\s]+structures?\b", re.I), "fee structure"),
    (re.compile(r"\bfees\b", re.I), "fee"),
    (re.compile(r"\bcut[-\s]*off\b", re.I), "cutoff"),
    (re.compile(r"\bwi-?fi\b", re.I), "wifi"),
    (re.compile(r"\banti[-\s]*ragging\b", re.I), "antiragging"),
    (re.compile(r"\bestablish\w*\b|\bfound(ed|er)?\b", re.I), "founded"),
    (re.compile(r"\blakh\b", re.I), "lakh"),
    (re.compile(r"\brupees?\b|\binr\b", re.I), "inr"),
    (re.compile(r"\bfests?\b|\bfestivals?\b", re.I), "festival"),
]

# Base manual synonyms
_RAW_SYNONYMS: dict[str, tuple[str, ...]] = {
    # --- hostel
    "accommodation": ("hostel", "dorm", "room"), "dorm": ("hostel", "accommodation"), "dormitory": ("hostel", "dorm"),
    "room": ("hostel", "accommodation"), "roommate": ("hostel",), "warden": ("hostel", "contact"),
    "mess": ("hostel", "food", "canteen", "dining"), "curfew": ("hostel", "timing", "entry", "exit"),
    "laundry": ("hostel", "facility"), "outing": ("hostel", "timing", "permission"),
    "guest": ("visitor", "hostel"), "parent": ("visitor", "guardian"),
    "overnight": ("hostel", "stay"), "entry": ("hostel", "timing", "curfew"), "exit": ("hostel", "timing", "curfew"),
    "visitor": ("hostel", "guest"),
    # --- fees
    "cost": ("fee", "price", "charge", "tuition"), "price": ("fee", "cost"), "charge": ("fee", "cost"),
    "tuition": ("fee", "academic"), "pay": ("fee", "payment", "installment"),
    "payment": ("fee", "pay", "deposit"), "expense": ("fee", "cost"), "deposit": ("fee", "caution"),
    "installment": ("fee", "payment"), "money": ("fee",), "afford": ("fee",),
    "refund": ("fee", "withdrawal", "policy"), "lakh": ("fee", "inr", "rupees"), "inr": ("fee", "rupees"),
    # --- admission
    "apply": ("admission", "application", "register"), "applying": ("admission", "application"),
    "admit": ("admission",), "enrol": ("admission", "registration"), "enroll": ("admission", "registration"),
    "enrollment": ("admission", "enrol"), "admission": ("apply", "application", "eligibility"),
    "register": ("admission", "application", "registration"), "join": ("admission", "seat"),
    "enter": ("admission",), "seat": ("admission", "intake"), "intake": ("admission", "seat"),
    "cutoff": ("admission", "eligibility", "score"), "percentile": ("admission", "jee", "cuet", "score"),
    "score": ("admission", "marks", "percentile"), "withdraw": ("admission", "refund"), "withdrawal": ("admission", "refund"),
    # --- documents
    "paper": ("document", "certificate"), "certificate": ("document", "certificate", "marksheet"),
    "requirement": ("document", "eligibility", "criteria"), "checklist": ("document", "admission", "registration"),
    "reporting": ("admission", "registration", "document"), "photocopy": ("document", "certificate"),
    "original": ("document", "certificate"), "aadhaar": ("identity", "document", "id"),
    "marksheet": ("document", "academic", "certificate"),
    # --- examination
    "exam": ("examination", "test", "grading"), "test": ("examination", "exam"),
    "examination": ("exam", "test", "grading", "marks"), "backlog": ("examination", "grade", "fail"),
    "grade": ("grading", "marks", "cgpa", "sgpa"), "marks": ("grading", "grade", "score"),
    "result": ("examination", "grade"), "attendance": ("examination", "rule", "detention"),
    "cgpa": ("grade", "sgpa", "gpa"), "sgpa": ("grade", "cgpa"), "gpa": ("grade", "cgpa"),
    "probation": ("examination", "rule", "academic"), "detention": ("examination", "rule", "attendance"),
    # --- scholarship
    "waiver": ("scholarship", "financial"), "aid": ("scholarship", "financial"),
    "financial": ("scholarship", "aid"), "stipend": ("scholarship",), "merit": ("scholarship",),
    "incentive": ("scholarship", "fee"), "scholarship": ("waiver", "aid", "merit", "concession"),
    # --- contact
    "phone": ("contact", "number", "call"), "call": ("contact", "phone"),
    "mail": ("contact", "email"), "email": ("contact", "mail"), "reach": ("contact",),
    "address": ("contact", "location"), "located": ("location", "campus", "address"),
    "location": ("campus", "contact", "address"), "registrar": ("contact", "office"),
    "helpline": ("contact", "phone"), "number": ("contact", "phone"),
    "contact": ("registrar", "admissions", "phone", "email"),
    "office": ("contact", "helpdesk"), "helpdesk": ("contact", "office"),
    # --- academics / programmes
    "branch": ("program", "specialization", "course"), "course": ("program", "curriculum", "syllabus"),
    "degree": ("program", "btech", "mtech", "bdes", "mdes", "bba", "phd"),
    "specialization": ("program", "branch"), "specialisation": ("specialization",),
    "syllabus": ("curriculum", "course"), "curriculum": ("syllabus", "course"),
    "semester": ("academics", "schedule", "calendar"), "credit": ("academics", "grade"),
    "faculty": ("academics", "professor", "teacher", "instructor"), "professor": ("faculty", "teacher"),
    "teacher": ("faculty", "professor"), "dean": ("faculty", "leadership"), "director": ("faculty", "leadership"),
    # --- notices
    "news": ("notice", "announcement"), "announcement": ("notice", "news"), "update": ("notice",),
    "circular": ("notice",), "recent": ("notice", "update"),
    # --- general / campus
    "facility": ("amenity", "campus", "infrastructure"), "amenity": ("facility", "campus"),
    "campus": ("facility", "infrastructure", "location", "amenity"),
    "infrastructure": ("campus", "facility"),
    "library": ("campus", "facility", "lrc"), "sports": ("campus", "facility", "spardha"),
    "gym": ("campus", "facility", "fitness"), "fitness": ("gym", "sports"),
    "canteen": ("campus", "food", "facility", "eateries"), "food": ("canteen", "mess", "eateries"),
    "eateries": ("cafeteria", "canteen", "food", "dining"),
    "transport": ("campus", "bus"), "bus": ("transport", "campus"),
    "wifi": ("campus", "facility", "internet"), "internet": ("campus", "wifi"),
    "medical": ("campus", "health", "clinic"), "health": ("medical", "campus", "clinic"),
    "clinic": ("medical", "health", "doctor"), "doctor": ("medical", "health", "clinic"),
    "ambulance": ("medical", "emergency", "health", "hospital"),
    "mindery": ("counselling", "mental", "health", "psychologist"),
    "counselling": ("mindery", "mental", "health", "therapy", "guidance"),
    "counseling": ("counselling", "mindery", "mental", "health"),
    "makerspace": ("prototyping", "fabrication", "lab", "facility"),
    "lab": ("campus", "facility", "makerspace"), "laboratory": ("lab",),
    "councils": ("student", "leadership", "governance", "council"),
    "council": ("student", "leadership", "governance"),
    "ragging": ("antiragging", "rule", "policy"), "antiragging": ("rule", "policy"),
    "grievance": ("rule", "contact", "sgrc"), "sgrc": ("grievance", "student"),
    "acres": ("campus", "infrastructure", "area"), "acre": ("campus", "infrastructure"),
    "size": ("campus", "acres", "area"), "area": ("campus", "acres"),
    "placement": ("campus", "career", "package", "ctc", "recruiters", "internship", "salary"),
    "placements": ("placement", "package", "ctc", "recruiters", "career"),
    "package": ("placement", "ctc", "salary", "lpa", "highest", "average"),
    "packages": ("package", "placement", "ctc"),
    "ctc": ("placement", "package", "salary", "lpa", "highest", "average"),
    "salary": ("placement", "package", "ctc"),
    "recruiter": ("placement", "company", "recruiters"),
    "recruiters": ("placement", "recruiter", "company", "companies"),
    "highest": ("maximum", "package", "ctc", "placement"),
    "average": ("package", "ctc", "placement", "salary"),
    "lpa": ("ctc", "package", "placement", "lakh"),
    "companies": ("placement", "recruiter"), "internship": ("campus", "career", "placement"),
    "exchange": ("international", "collaboration", "cglp"),
    "abroad": ("international", "exchange"), "cglp": ("exchange", "international"),
    "partner": ("collaboration", "exchange"), "collaboration": ("international", "partner"),
    # --- events & festivals (fully linked)
    "event": ("festival", "cultural", "sports", "fest", "sabrang", "spardha", "hackjklu", "aarambh", "aarohan", "jaipur design week", "sangam", "parichay"),
    "events": ("festival", "cultural", "sports", "fest", "sabrang", "spardha", "hackjklu", "aarambh", "aarohan", "jaipur design week", "sangam", "parichay"),
    "fest": ("event", "festival", "cultural", "sports", "sabrang", "spardha", "hackjklu", "aarambh", "aarohan", "jaipur design week", "sangam", "parichay"),
    "fests": ("event", "festival", "cultural", "sports", "sabrang", "spardha", "hackjklu", "aarambh", "aarohan", "jaipur design week", "sangam", "parichay"),
    "festival": ("event", "fest", "cultural", "sports", "sabrang", "spardha", "hackjklu", "aarambh", "aarohan", "jaipur design week", "sangam", "parichay"),
    "festivals": ("event", "fest", "cultural", "sports", "sabrang", "spardha", "hackjklu", "aarambh", "aarohan", "jaipur design week", "sangam", "parichay"),
    "sabrang": ("festival", "cultural", "event", "music", "dance", "drama"),
    "aarambh": ("induction", "orientation", "freshers", "festival", "event"),
    "hackjklu": ("hackathon", "coding", "event", "competition", "tech"),
    "hackathon": ("hackjklu", "coding", "competition", "tech"),
    "spardha": ("sports", "festival", "tournament", "athletic", "competition"),
    "aic": ("incubation", "startup", "entrepreneurship", "innovation"),
    "incubation": ("aic", "startup", "entrepreneurship"),
    "parichay": ("induction", "talent", "showcase", "freshers", "event"),
    "sangam": ("conclave", "industry", "academia", "event"),
    "aarohan": ("leadership", "entrepreneurship", "summit", "event"),
    "laureate": ("awards", "honours", "leadership", "recognition"),
    # --- misc
    "regulation": ("rule", "policy"), "rule": ("regulation", "policy"),
    "yearly": ("annual",), "annual": ("yearly", "yearly"), "annually": ("annual",),
    "criteria": ("eligibility", "requirement"), "qualification": ("eligibility",),
    "qualify": ("eligibility",), "eligible": ("eligibility",),
    "process": ("procedure", "application", "step"), "procedure": ("process", "step"),
    "step": ("process", "procedure"),
    "founded": ("history", "general"), "history": ("general",),
    "ranking": ("general", "accreditation"), "accreditation": ("general", "ranking"),
    "naac": ("accreditation",), "nirf": ("ranking",),
}


def _symmetrize_synonyms(raw: dict[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
    """Build a fully symmetric bidirectional synonym graph.
    If A is a synonym of B, B is guaranteed to be a synonym of A.
    """
    graph: dict[str, set[str]] = {}
    for word, syn_tuple in raw.items():
        w = word.strip().lower()
        if not w:
            continue
        graph.setdefault(w, set())
        for s in syn_tuple:
            s_clean = s.strip().lower()
            if not s_clean or s_clean == w:
                continue
            graph[w].add(s_clean)
            graph.setdefault(s_clean, set()).add(w)
    return {k: tuple(sorted(v)) for k, v in graph.items()}


# Fully bidirectional synonym graph
SYNONYMS: dict[str, tuple[str, ...]] = _symmetrize_synonyms(_RAW_SYNONYMS)


COMMON_TYPOS: dict[str, str] = {
    # Greetings & Self-Introduction
    "hii": "hi", "hiii": "hi", "hiiii": "hi", "heyy": "hey", "heya": "hey", "hellow": "hello", "helloo": "hello",
    # Programming & Outside Terms
    "fibbonacci": "fibonacci", "fibonaci": "fibonacci", "fibonocci": "fibonacci", "fibb": "fibonacci",
    # Events & Festivals
    "sabrag": "sabrang", "sabran": "sabrang", "subrang": "sabrang",
    "arambh": "aarambh", "aramb": "aarambh", "aaramb": "aarambh",
    "hakjklu": "hackjklu", "hackklu": "hackjklu", "hackathon": "hackjklu", "hackthon": "hackjklu",
    "spardha": "spardha", "sparda": "spardha", "saprdha": "spardha",
    "parichy": "parichay", "parichya": "parichay",
    "sangm": "sangam", "sangama": "sangam",
    "arohan": "aarohan", "arohan": "aarohan",
    "laurate": "laureate", "laurat": "laureate",
    # Campus, Facilities & Health
    "hosetl": "hostel", "hostal": "hostel", "hostle": "hostel", "hostels": "hostel", "hosteller": "hostel",
    "campas": "campus", "campuss": "campus", "cumpus": "campus",
    "cantin": "canteen", "cantean": "canteen", "catin": "canteen",
    "libary": "library", "librery": "library", "libarary": "library",
    "academiks": "academics", "acadmic": "academic", "acdmics": "academics",
    "faculity": "faculty", "faclty": "faculty", "facculty": "faculty",
    "makrspace": "makerspace", "makerspc": "makerspace",
    "mindry": "mindery", "minderi": "mindery",
    "counceling": "counselling", "counselor": "counsellor", "counseller": "counsellor",
    "ambulence": "ambulance", "ambulnce": "ambulance",
    "cashfre": "cashfree", "cashfrea": "cashfree",
    "curefw": "curfew", "curfiew": "curfew", "curfeww": "curfew",
    "mes": "mess", "messs": "mess",
    # Fees & Finance
    "fe": "fee", "feee": "fee", "feeee": "fee", "structur": "structure",
    "tution": "tuition", "tuiton": "tuition", "tiution": "tuition",
    "scholorship": "scholarship", "schollarship": "scholarship", "scholarhip": "scholarship",
    "deposite": "deposit", "depost": "deposit", "refnd": "refund", "refunt": "refund",
    # Admissions, Academics & Documents
    "admisson": "admission", "adimission": "admission", "admissin": "admission",
    "eligiblity": "eligibility", "eligibilty": "eligibility", "elgibility": "eligibility",
    "regestration": "registration", "registraion": "registration", "regsitration": "registration",
    "curiculam": "curriculum", "curiculum": "curriculum", "cirriculum": "curriculum",
    "attendence": "attendance", "attandance": "attendance", "atendance": "attendance",
    "professer": "professor", "profeser": "professor", "professr": "professor",
    "plcement": "placement", "placemnt": "placement", "placment": "placement", "placementss": "placement",
    "pacakge": "package", "packge": "package", "pakage": "package",
    "internhip": "internship", "internshp": "internship",
    "sylabus": "syllabus", "syllubus": "syllabus",
    "adhaar": "aadhaar", "adhar": "aadhaar", "aadhar": "aadhaar",
    "checlist": "checklist", "checklst": "checklist",
    "provisonal": "provisional", "migraton": "migration",
}

DOMAIN_KEYWORDS: tuple[str, ...] = tuple(sorted(set(list(COMMON_TYPOS.values()) + [
    "sabrang", "aarambh", "hackjklu", "spardha", "incubation", "parichay", "sangam", "aarohan", "laureate",
    "hostel", "warden", "campus", "canteen", "library", "sports", "eateries", "curfew", "roommate", "laundry",
    "tuition", "scholarship", "deposit", "refund", "registration", "cashfree", "installment",
    "admission", "eligibility", "curriculum", "attendance", "examination", "probation", "backlog",
    "placement", "internship", "professor", "faculty", "registrar", "recruiter", "package", "salary",
    "makerspace", "mindery", "counselling", "ambulance", "councils", "aadhaar", "checklist", "marksheet",
    "engineering", "technology", "design", "management", "computer", "electronics", "btech", "mtech", "bdes", "mdes", "bba", "phd",
    "festival", "festivals", "event", "events", "tournament", "competition", "conclave", "auditorium", "transport"
])))

DOMAIN_KEYWORDS_SET = frozenset(DOMAIN_KEYWORDS)


def _edit_distance(s1: str, s2: str, max_dist: int = 2) -> int:
    """Fast Damerau-Levenshtein edit distance bounded by max_dist."""
    len1, len2 = len(s1), len(s2)
    if abs(len1 - len2) > max_dist:
        return max_dist + 1
    prev = list(range(len2 + 1))
    for i, c1 in enumerate(s1, 1):
        curr = [i] + [0] * len2
        for j, c2 in enumerate(s2, 1):
            cost = 0 if c1 == c2 else 1
            curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[len2]


def correct_typos(text: str) -> str:
    """Autocorrect common student typos, repeated characters, and misspellings against university vocabulary."""
    if not text:
        return text
    # Compress 3+ repeated characters (e.g. 'feeee' -> 'fee', 'hostellll' -> 'hostel')
    text = re.sub(r"(.)\1{2,}", r"\1\1", text)
    words = text.split()
    corrected = []
    for w in words:
        clean = re.sub(r"^\W+|\W+$", "", w).lower()
        if not clean or clean in STOPWORDS or clean in _PROTECTED:
            corrected.append(w)
            continue
        # 1. Direct dictionary match
        if clean in COMMON_TYPOS:
            rep = COMMON_TYPOS[clean]
            corrected.append(w.lower().replace(clean, rep))
            continue
        # 2. Bounded edit distance on domain vocabulary
        if len(clean) >= 4 and clean not in DOMAIN_KEYWORDS_SET:
            best_match = None
            best_dist = 3
            clean_len = len(clean)
            for kw in DOMAIN_KEYWORDS:
                if abs(len(kw) - clean_len) > 2:
                    continue
                d = _edit_distance(clean, kw, max_dist=2)
                if d == 1 or (d == 2 and clean_len >= 6):
                    if d < best_dist:
                        best_dist = d
                        best_match = kw
                        if d == 1:
                            break
            if best_match:
                corrected.append(w.lower().replace(clean, best_match))
                continue
            # 3. Fuzzy match fallback
            matches = difflib.get_close_matches(clean, DOMAIN_KEYWORDS, n=1, cutoff=0.78)
            if matches:
                corrected.append(w.lower().replace(clean, matches[0]))
                continue
        corrected.append(w)
    return " ".join(corrected)


# Generic words that on their own do not identify what the user wants
GENERIC_HEADS = frozenset("""
fee fees deadline deadlines date dates eligibility scholarship scholarships hostel admission admissions
exam exams examination notice notices program programs course courses document documents
requirement requirements rule rules policy policies timing timings schedule procedure process
""".split())


def normalise(text: str) -> str:
    text = correct_typos(text or "").lower()
    for rx, rep in _NORMALISE:
        text = rx.sub(rep, text)
    return text


_TOKEN = re.compile(r"[a-z0-9]+")

_PROTECTED = frozenset({
    "bdes", "mdes", "btech", "mtech", "bba", "phd", "ces", "ece", "eee", "cse",
    "wifi", "naac", "nirf", "sgpa", "cgpa", "nata", "uceed", "cuet", "gate", "jee", "det",
})


_IRREGULAR_ROOTS: dict[str, str] = {
    # Verbs & Tenses
    "taught": "teach", "teaches": "teach", "teaching": "teach", "teacher": "teach", "teachers": "teach",
    "held": "hold", "holding": "hold", "holds": "hold",
    "paid": "pay", "paying": "pay", "payment": "pay", "payments": "pay", "pays": "pay",
    "applied": "apply", "applies": "apply", "applying": "apply", "applicant": "apply", "applicants": "apply", "application": "apply", "applications": "apply",
    "admitted": "admit", "admits": "admit", "admitting": "admit", "admission": "admit", "admissions": "admit",
    "enrolled": "enroll", "enrolling": "enroll", "enrollment": "enroll", "enrolls": "enroll",
    "registered": "register", "registering": "register", "registration": "register", "registers": "register",
    "examined": "exam", "examining": "exam", "examination": "exam", "examinations": "exam", "exams": "exam",
    "placed": "placement", "placing": "placement", "placements": "placement",
    "graduated": "graduate", "graduating": "graduate", "graduation": "graduate", "graduates": "graduate",
    "evaluated": "evaluate", "evaluating": "evaluate", "evaluation": "evaluate",
    "attended": "attend", "attending": "attend", "attendance": "attend",
    "studied": "study", "studies": "study", "studying": "study",
    "celebrated": "celebrate", "celebrates": "celebrate", "celebrating": "celebrate", "celebration": "celebrate", "celebrations": "celebrate",
    "organized": "organize", "organizes": "organize", "organizing": "organize", "organization": "organize",
    "competed": "compete", "competes": "compete", "competing": "compete", "competition": "compete", "competitions": "compete",
    "participated": "participate", "participating": "participate", "participation": "participate", "participants": "participate",
    "accommodated": "accommodate", "accommodation": "accommodate", "accommodations": "accommodate",
    "sponsored": "sponsor", "sponsoring": "sponsor", "sponsorship": "sponsor",
    "founded": "found", "founder": "found", "foundation": "found",
    "established": "establish", "establishing": "establish", "establishment": "establish",
    "innovated": "innovate", "innovating": "innovate", "innovation": "innovate", "innovations": "innovate",
    "incubated": "incubate", "incubating": "incubate", "incubation": "incubate", "incubator": "incubate",
    
    # Nouns & Plurals & Variants
    "criteria": "criterion", "criterion": "criterion",
    "curricula": "curriculum", "curriculums": "curriculum", "curriculum": "curriculum",
    "syllabi": "syllabus", "syllabuses": "syllabus", "syllabus": "syllabus",
    "alumni": "alumni", "alumnus": "alumni", "alumna": "alumni",
    "fests": "festival", "fest": "festival", "festivals": "festival", "festival": "festival",
    "events": "event", "event": "event",
    "fees": "fee", "fee": "fee",
    "hostels": "hostel", "hostel": "hostel", "hostellers": "hostel", "hostelites": "hostel",
    "scholarships": "scholarship", "scholarship": "scholarship",
    "programmes": "program", "programs": "program", "programme": "program", "program": "program",
    "courses": "course", "course": "course",
    "degrees": "degree", "degree": "degree",
    "branches": "branch", "branch": "branch",
    "professors": "professor", "professor": "professor", "profs": "professor", "prof": "professor",
    "deans": "dean", "dean": "dean",
    "directors": "director", "director": "director",
    "librarians": "library", "libraries": "library", "library": "library",
    "laboratories": "lab", "labs": "lab", "laboratory": "lab", "lab": "lab",
    "activities": "activity", "activity": "activity",
    "facilities": "facility", "facility": "facility",
    "amenities": "amenity", "amenity": "amenity",
    "policies": "policy", "policy": "policy",
    "regulations": "rule", "rules": "rule", "rule": "rule", "regulation": "rule",
    "procedures": "procedure", "procedure": "procedure",
    "processes": "process", "process": "process",
    "eligibilities": "eligibility", "eligibility": "eligibility",
    "companies": "company", "company": "company",
    "recruiters": "recruiter", "recruiter": "recruiter",
    "packages": "package", "package": "package",
    "salaries": "salary", "salary": "salary",
    "tournaments": "tournament", "tournament": "tournament",
    "sports": "sport", "sport": "sport",
    "games": "game", "game": "game",
    "societies": "club", "clubs": "club", "society": "club", "club": "club",
    "children": "child", "child": "child",
}


@lru_cache(maxsize=100000)
def _porter_stem(w: str) -> str:
    """Improved Porter-style stemmer with broader suffix handling."""
    if len(w) <= 3 or w.isdigit() or w in _PROTECTED:
        return w
    # Step 1: plural / irregular endings
    if w.endswith("ies") and len(w) > 4:
        w = w[:-3] + "y"
    elif w.endswith("sses"):
        w = w[:-2]
    elif w.endswith("s") and not w.endswith(("ss", "us", "is", "as", "es")):
        w = w[:-1]
    # Step 2: gerund / past tense
    if len(w) > 6 and w.endswith("ing"):
        core = w[:-3]
        if len(core) >= 3:
            w = core
    elif len(w) > 5 and w.endswith("ed"):
        core = w[:-2]
        if len(core) >= 3:
            w = core
    # Step 3: derivational suffixes (longest match first)
    if len(w) > 7 and w.endswith("ational"):
        w = w[:-7] + "ate"
    elif len(w) > 6 and w.endswith("ation"):
        w = w[:-5] + "ate"
    elif len(w) > 5 and w.endswith("ness"):
        w = w[:-4]
    elif len(w) > 5 and w.endswith("ment"):
        w = w[:-4]
    elif len(w) > 5 and w.endswith("ful"):
        w = w[:-3]
    elif len(w) > 5 and w.endswith("ity"):
        w = w[:-3]
    elif len(w) > 5 and w.endswith("ive"):
        w = w[:-3]
    elif len(w) > 5 and w.endswith("al"):
        w = w[:-2]
    elif len(w) > 4 and w.endswith("er"):
        w = w[:-2]
    # Step 4: trailing silent -e
    if len(w) > 4 and w.endswith("e"):
        w = w[:-1]
    return w


@lru_cache(maxsize=100000)
def get_root_word(w: str) -> str:
    """Extract canonical root word (stem / lemma) for robust comparison."""
    if not w or len(w) <= 2 or w.isdigit() or w in _PROTECTED:
        return w
    clean = w.lower().strip()
    if clean in _IRREGULAR_ROOTS:
        return _IRREGULAR_ROOTS[clean]
    return _porter_stem(clean)


# Alias stem to get_root_word so tokenizing, evidence checking, and indexing all compare root words
stem = get_root_word


GENERIC_HEAD_STEMS = frozenset(stem(w) for w in GENERIC_HEADS)


def tokens(text: str, keep_stop: bool = False) -> list[str]:
    out = []
    for t in _TOKEN.findall(normalise(text)):
        if not keep_stop and t in STOPWORDS:
            continue
        out.append(stem(t))
    return out


def bigram_tokens(text: str) -> list[str]:
    """Unigrams + bigrams for richer BM25 phrase matching (e.g. 'hostel fee', 'registrar phone')."""
    toks = tokens(text)
    bigrams = [f"{a}__{b}" for a, b in zip(toks, toks[1:])]
    return toks + bigrams


def content_terms(question: str) -> list[str]:
    """Unique stemmed content words of a question, in order."""
    seen, out = set(), []
    for t in tokens(question):
        if t not in seen and (len(t) > 1 or t.isdigit()):
            seen.add(t)
            out.append(t)
    return out


_syn_stem_graph: dict[str, set[str]] = {}
for _k, _v in SYNONYMS.items():
    _k_root = get_root_word(normalise(_k).strip())
    _v_roots = {get_root_word(x) for x in _v if get_root_word(x) != _k_root}
    _syn_stem_graph.setdefault(_k_root, set()).update(_v_roots)
    for _vr in _v_roots:
        _syn_stem_graph.setdefault(_vr, set()).add(_k_root)

_SYN_STEMMED: dict[str, tuple[str, ...]] = {k: tuple(sorted(v)) for k, v in _syn_stem_graph.items()}


def synonym_stems(term: str) -> tuple[str, ...]:
    """Stemmed synonyms/related concepts for an (already stemmed) term."""
    return _SYN_STEMMED.get(term, ())


def expand_terms(terms: list[str]) -> list[str]:
    """Add domain synonyms (used for the BM25 query only)."""
    out = list(terms)
    seen = set(terms)
    for t in terms:
        for s in synonym_stems(t):
            if s not in seen:
                seen.add(s)
                out.append(s)
    return out


# ---------------------------------------------------------------- routing
_ROUTES: list[tuple[str, re.Pattern]] = [
    ("hostel", re.compile(
        r"\b(hostel|mess|warden|roommate|dorm\w*|accommodation|visitors?|curfew|room|laundry|"
        r"entry|exit|outing|pg\b|paying guest|boarding|wardrobe|almirah|study table|study desk|"
        r"housekeeping|laundry facility|ro water)\b", re.I)),
    ("fees", re.compile(
        r"\b(fees?|tuition|charges?|cost|refund|payment|deposit|installment|price|pay|lakh|inr|rupees?)\b", re.I)),
    ("scholarships", re.compile(
        r"\b(scholarships?|waiver|financial aid|aid|stipend|merit|incentive|financial assistance|family income|need-based)\b", re.I)),
    # contact is checked BEFORE admission so that "contact the admissions office" / "phone number of the
    # Registrar" route to the contact-us page rather than admission brochures.
    ("contact", re.compile(
        r"\b(contact|phone|call|email|e-mail|address|registrar|location|located|reach|"
        r"office|helpline|number|helpdesk|whatsapp|mindery|counsell?ing contact|ambulance contact|"
        r"emergency contacts?|campus security|security control room|fire safety|maintenance department)\b", re.I)),
    ("admission", re.compile(
        r"\b(admissions?|apply|application|eligib\w*|entrance|jee|cuet|det|nata|uceed|"
        r"lateral|international|documents?|enrol\w*|withdraw\w*|cut-?off|percentile|12th|xii|class 12|"
        r"get into|join|joining|reporting|checklist|original|photocopy|seats?|intake|score|"
        r"aadhaar|marksheet|migration|transfer certificate|\btc\b|provisional|gap[- ]year|affidavit|"
        r"medical fitness|anti-?ragging undertaking|physics|chemistry|mathematics|pcm\b|compartment)\b", re.I)),
    ("examination", re.compile(
        r"\b(exams?|examinations?|grad(e|es|ing)|cgpa|sgpa|gpa|attendance|backlog|"
        r"re-?exam|detain\w*|probation|academically deficient|marks|results?|mid-?term|"
        r"end-?term|supplementary|credits?)\b", re.I)),
    ("faculty", re.compile(
        r"\b(facult\w*|professors?|teachers?|deans?|directors?|vice chancellor|vc\b|hod\b|"
        r"who teaches|who is teaching|educators?|instructors?|faculty member|ph\.?d\.? guide)\b", re.I)),
    ("academics", re.compile(
        r"\b(programmes?|programs?|courses?|curricul\w*|department|specializ\w*|"
        r"specialis\w*|branch|calendars?|semester|syllabus|degree|institute|"
        r"exchange|study abroad|cglp|collaborat\w*|partner university|"
        r"b\.?tech|m\.?tech|b\.?des|m\.?des|bba|phd|ph\.d|"
        r"ai engineer|artificial intelligence|machine learning|data structures|cybersecurity|interdisciplinary|"
        r"library rules?|borrowing rules?|overdue|late fine|digital library|seminar halls?|auditorium|"
        r"placements?|package|packages|highest package|average package|ctc|highest ctc|average ctc|"
        r"recruiters?|salary|internships?|job offer)\b", re.I)),
    ("notices", re.compile(
        r"\b(notices?|announcements?|news|latest|circulars?|recent)\b", re.I)),
    ("general", re.compile(
        r"\b(campus|infrastruct\w*|facilit\w*|amenit\w*|vision|mission|about|history|naac|accredit\w*|"
        r"events?|fests?|festivals?|celebrations?|competitions?|"
        r"ranking|founded|chancellor|leadership|governance|library|sports?|placements?|internships?|"
        r"labs?|clubs?|societ\w*|wi-?fi|wifi|transport|bus|canteen|medical|gym|ragging|grievance|anti-?ragging|"
        r"nirf|acres|established|located\b|30 acres|package|highest package|average package|ctc|recruiters?|"
        r"sabrang|aarambh|hack\s*jklu|hackjklu|spardha|parichay|sangam|aarohan|jaipur design week|design guru day|"
        r"laureate awards?|aic|incubation|atal incubation|makerspace|design studios?|learning resource centre|lrc|"
        r"mp ranjan|eateries|fitness centre|student councils?|academic affairs council|campus life council|"
        r"cultural affairs council|technical council|sports council|public relations council|pr council|"
        r"health centre|ambulance|blue circle|mindery|mental health|counsell?ing|"
        r"placement registration|placement documents?|placement eligibility|placement preparation|"
        r"mock interviews?|career profile|career support|student support|faculty mentoring|academic advising|"
        r"student grievances?|sgrc|smart classrooms?|ai/ml computing|student activity centre|sac\b|"
        r"emergency facilities|fire safety equipment|first-?aid)\b", re.I)),
]


def route_categories(question: str) -> list[str]:
    """Rule-based query classifier -> list of likely categories (most specific first)."""
    q = normalise(question or "")
    return [cat for cat, rx in _ROUTES if rx.search(q)]


# Intent types
INTENT_JKLU = "jklu"
INTENT_ACADEMIC = "academic"
INTENT_MIXED = "mixed"
INTENT_IRRELEVANT = "irrelevant"

_JKLU_EXPLICIT_RX = re.compile(
    r"\b(jklu|jk lakshmipat|lakshmipat|campus|curfew|mess|hostel|fees?|admission|placements?|chancellor|vice chancellor)\b",
    re.I
)

_ACADEMIC_CONCEPT_RX = re.compile(
    r"\b(what is|explain|define|how does|difference between|pros and cons of|example of)\b.*\b("
    r"recursion|polymorphism|inheritance|binary search|sorting|algorithm|data structure|tree|graph|"
    r"operating system|deadlock|semaphore|virtual memory|paging|cache|"
    r"dbms|normalization|acid properties|sql|indexing|foreign key|"
    r"machine learning|neural network|deep learning|gradient descent|overfitting|underfitting|"
    r"convolution|transformer|attention mechanism|supervised learning|unsupervised learning|"
    r"tcp|udp|osi model|ip addressing|subnetting|dns|http|https|"
    r"calculus|eigenvalue|eigenvector|matrix multiplication|differential equation)\b",
    re.I
)

_IRRELEVANT_RX = re.compile(
    r"\b(movie|movies|film|films|recipe|chocolate cake|bake|baking|capital of france|who is the president of|fifa|world cup|cricket team|celebrity|lyrics)\b",
    re.I
)


from dataclasses import dataclass, field

@dataclass
class QueryAnalysis:
    raw_query: str
    primary_query: str
    sub_questions: list[str]
    retrieval_queries: list[str]
    intent: str
    unrelated_parts: list[str]
    is_off_topic_only: bool
    entities: dict = field(default_factory=dict)
    routed_categories: list[str] = field(default_factory=list)


_UNRELATED_RX = re.compile(
    r"\b(?:suggest|recommend|give me|tell me|show me|watch|write|generate|create)\s+(?:(?:a|an|some|the)\s+)?(?:\w+\s+)?(?:movie|movies|film|films|song|songs|joke|jokes|recipe|cake|weather|code|program|script|story|poem)\b|"
    r"\b(?:movie|movies|film|films|joke|jokes|song|songs|recipe|cake|bake|baking|weather)\b",
    re.I
)

_OFF_TOPIC_RX = re.compile(
    r"\b(?:fibonacci|prime\s+numbers?|factorial|palindrome|armstrong|bubble\s+sort|quick\s+sort|merge\s+sort|binary\s+search)\b|"
    r"\b(?:(?:write|give|show|create|generate|provide)\s+(?:(?:a|an|the|me)\s+)?(?:code|program|script|function|algorithm)|code\s+of|program\s+for|script\s+for)\b|"
    r"\b(?:(?:write|tell|generate|create)\s+(?:(?:a|an|the|me)\s+)?(?:story|poem|essay|song|joke|riddle))\b|"
    r"\b(?:solve|calculate|evaluate)\b.*(?:\d+|equation|expression|math)|"
    r"\b(photosynthesis|mitochondria|solar system|quantum mechanics|black hole)\b|"
    r"\b(fifa|world cup|cricket team|cricket score|chocolate cake|recipe|bake|baking|capital of [a-z]+|"
    r"who is the president of|who is the prime minister of|who won the|who is the ceo of|ceo of|"
    r"weather today|weather in|actor|actress|bollywood|hollywood|lyrics|bitcoin|crypto|stock price|"
    r"movie|movies|film|films|joke|jokes|song|songs|youtube video)\b",
    re.I
)

_CLAUSE_SPLIT_RX = re.compile(
    r"(?:,\s*|\s+)\b(?:and\s+also\b|also\b|as\s+well\s+as\b|and\s+what\b|and\s+who\b|and\s+how\b|and\s+where\b|and\s+when\b|and\s+why\b|and\s+which\b|and\s+can\s+you\b|and\s+tell\s+me\b|and\s+give\s+me\b|and\s+give\b|and\s+write\b|and\s+show\s+me\b|and\s+suggest\b|and\s+recommend\b|and\s+solve\b|and\s+explain\b|and\s+code\b|plus\b|along\s+with\b|by\s+the\s+way\b|additionally\b|furthermore\b)\b|[;?.]\s*",
    re.I
)

_UNIVERSITY_HINTS = re.compile(
    r"\b(jklu|university|college|campus|faculty|professor|professors|teacher|teachers|teach|teaches|department|dean|director|hod|leadership|"
    r"cse|computer science|ece|electronics|mechanical|iet|b\.?tech|m\.?tech|b\.?des|m\.?des|bba|phd|"
    r"attendance|semester|calendar|exam|examination|grade|grading|cgpa|sgpa|backlog|"
    r"fee|fees|tuition|hostel|mess|room|curfew|warden|scholarship|admission|eligibility|"
    r"placement|placements|internship|package|library|lrc|eateries|canteen|clinic|ambulance|"
    r"sabrang|spardha|hackjklu|aarambh|aarohan|sangam|parichay|festival|festivals|event|events|"
    r"rule|rules|policy|policies|guideline|guidelines|mentor|mentoring|grievance|sgrc)\b",
    re.I
)

_DEPT_PATTERNS = [
    (re.compile(r"\b(cse|computer science|computer science & engineering|computer science and engineering)\b", re.I),
     "Computer Science and Engineering"),
    (re.compile(r"\b(ece|electronics|electronics & communication|electronics and communication)\b", re.I),
     "Electronics & Communication Engineering"),
    (re.compile(r"\b(design|b\.?des|m\.?des|product design|interaction design|communication design)\b", re.I),
     "Institute of Design"),
    (re.compile(r"\b(management|bba|business administration|finance|marketing)\b", re.I),
     "Institute of Management"),
    (re.compile(r"\b(ccct|communication and critical thinking)\b", re.I),
     "Centre for Communication and Critical Thinking (CCCT)"),
    (re.compile(r"\b(math|mathematics|applied science)\b", re.I),
     "Mathematics"),
]


def understand_query(question: str, history: list[dict] | None = None) -> QueryAnalysis:
    """Analyze query to isolate genuine JKLU requests, strip conversational noise, and extract entities."""
    raw = (question or "").strip()
    corrected = correct_typos(raw)

    # 1. Split unrelated trailing/secondary non-university requests (e.g. "suggest a movie")
    unrelated: list[str] = []
    valid_parts: list[str] = []
    clauses = _CLAUSE_SPLIT_RX.split(corrected)
    for cl in clauses:
        cl_str = cl.strip(" ?.,")
        if not cl_str or len(cl_str) < 3:
            continue
        is_univ = bool(_UNIVERSITY_HINTS.search(cl_str)) or bool(route_categories(cl_str))
        is_off = bool(_OFF_TOPIC_RX.search(cl_str)) or bool(_UNRELATED_RX.search(cl_str))
        if is_off and not is_univ:
            unrelated.append(cl_str)
        elif not is_univ and re.search(r"\b(who is|what is the capital|recipe for|weather in|tell me a joke|recommend a movie|capital of|code for|code of|program for|program of|solve \d|story about)\b", cl_str, re.I):
            unrelated.append(cl_str)
        elif not is_univ and re.search(r"^\s*(?:\d+[\s\+\-\*\/x=]+\d+|\w+[\s\+\-\*\/=]+\d+)", cl_str):
            unrelated.append(cl_str)
        else:
            valid_parts.append(cl_str)

    if not valid_parts:
        # Query contains only off-topic text
        return QueryAnalysis(
            raw_query=raw,
            primary_query=raw,
            sub_questions=[],
            retrieval_queries=[raw],
            intent=INTENT_IRRELEVANT,
            unrelated_parts=[raw],
            is_off_topic_only=True,
            entities={},
            routed_categories=[],
        )

    working_q = " ".join(valid_parts).strip()

    # 2. Extract after conversational preamble connectors (e.g., "I'm trying to plan my semester... but can you tell me...")
    m = re.search(
        r"\b(?:but|so|however|then)\s*,?\s*(?:can\s+you\s+(?:please\s+)?tell\s+me\s+|could\s+you\s+(?:please\s+)?tell\s+me\s+|please\s+tell\s+me\s+|tell\s+me\s+|what\s+is\s+|what\s+are\s+|when\s+does\s+|where\s+is\s+|who\s+teaches\s+|who\s+are\s+|which\s+.*|how\s+.*)(.*)$",
        working_q,
        re.I
    )
    if m:
        match_start = m.start()
        sub = working_q[match_start:]
        sub = re.sub(r"^(?:but|so|however|then)\s*,?\s*", "", sub, flags=re.I).strip()
        lead_stripped = re.sub(
            r"^(?:can\s+you\s+(?:please\s+)?tell\s+me\s+|could\s+you\s+(?:please\s+)?tell\s+me\s+|please\s+tell\s+me\s+|tell\s+me\s+)",
            "", sub, flags=re.I
        ).strip()
        if lead_stripped and len(lead_stripped.split()) >= 3 and _UNIVERSITY_HINTS.search(lead_stripped):
            primary = lead_stripped[0].upper() + lead_stripped[1:]
            if not primary.endswith("?"):
                primary += "?"
        else:
            primary = sub[0].upper() + sub[1:]
    else:
        # Check for direct leading "can you tell me" / "please tell me"
        lead_stripped = re.sub(
            r"^(?:can\s+you\s+(?:please\s+)?tell\s+me\s+|could\s+you\s+(?:please\s+)?tell\s+me\s+|please\s+tell\s+me\s+)",
            "", working_q, flags=re.I
        ).strip()
        if lead_stripped and len(lead_stripped.split()) >= 3 and _UNIVERSITY_HINTS.search(lead_stripped):
            primary = lead_stripped[0].upper() + lead_stripped[1:]
        else:
            primary = working_q

    # 3. Detect multiple genuine sub-questions (e.g. "What is the fee and what is the hostel curfew?")
    sub_questions: list[str] = []
    multi_parts = re.split(r"\b(?:and|as well as|also)\b|\band\s+what\b|\band\s+how\b|\band\s+when\b", primary, flags=re.I)
    multi_parts = [p.strip(" ?.,") for p in multi_parts if len(p.strip()) > 3]
    if len(multi_parts) >= 2 and all(_UNIVERSITY_HINTS.search(p) for p in multi_parts):
        sub_questions = [p[0].upper() + p[1:] + ("?" if not p.endswith("?") else "") for p in multi_parts]

    # 4. Extract Entities
    entities: dict = {"departments": [], "topics": [], "faculty_names": []}
    for m in re.finditer(r"\b(?:dr\.?|prof(?:essor)?\.?)\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)+)", working_q, re.I):
        entities["faculty_names"].append(m.group(1).strip())
    for rx, dept_name in _DEPT_PATTERNS:
        if rx.search(primary):
            entities["departments"].append(dept_name)

    routed = route_categories(primary)
    if "faculty" in routed:
        entities["topics"].append("faculty")
    if "examination" in routed:
        entities["topics"].append("examination/attendance")
    if "hostel" in routed:
        entities["topics"].append("hostel")
    if "fees" in routed:
        entities["topics"].append("fees")
    if "academics" in routed:
        entities["topics"].append("academics/calendar")

    # 5. Dual Retrieval Formulations
    retrieval_queries = [primary]
    if primary.lower() != raw.lower() and not unrelated:
        retrieval_queries.append(raw)
    if entities["departments"] and "faculty" in routed:
        retrieval_queries.append(f"faculty members {entities['departments'][0]} JKLU")

    q_lower = primary.lower()
    if ("physics" in q_lower or "pcm" in q_lower) and ("mathematics" in q_lower or "math" in q_lower or "compulsory" in q_lower or "eligib" in q_lower):
        retrieval_queries.append("Bachelor of Technology B.Tech aggregate English Mathematics Physics and Chemistry class XII eligibility")
    if "ai engineer" in q_lower or ("become" in q_lower and "ai" in q_lower):
        retrieval_queries.append("B.Tech Computer Science and Engineering AI Artificial Intelligence and Machine Learning specialization curriculum")
    if "contradict" in q_lower and "academic" in q_lower:
        retrieval_queries.append("academic regulations guidelines award of grades JKLU official documents")
    if any(w in q_lower for w in ("fest", "festival", "fests", "festivals", "event", "events")):
        if any(w in q_lower for w in ("held", "organized", "celebrat", "annual", "happen", "campus", "jklu", "university", "what are", "which are", "list")):
            retrieval_queries.append("annual festivals cultural sports events Sabrang Spardha HackJKLU Aarambh JKLU")

    # Intent classification
    intent = classify_query_intent(primary)

    return QueryAnalysis(
        raw_query=raw,
        primary_query=primary,
        sub_questions=sub_questions,
        retrieval_queries=retrieval_queries,
        intent=intent,
        unrelated_parts=unrelated,
        is_off_topic_only=False,
        entities=entities,
        routed_categories=routed,
    )


def classify_query_intent(question: str) -> str:
    """Determine whether the query is JKLU-specific, academic concept, mixed, or irrelevant."""
    q = (question or "").strip()
    has_academic = bool(_ACADEMIC_CONCEPT_RX.search(q))
    has_jklu = bool(_JKLU_EXPLICIT_RX.search(q)) or bool(_UNIVERSITY_HINTS.search(q))
    if has_jklu or has_academic:
        if has_academic and has_jklu:
            return INTENT_MIXED
        if has_academic:
            return INTENT_ACADEMIC
        return INTENT_JKLU
    if _IRRELEVANT_RX.search(q) or _OFF_TOPIC_RX.search(q):
        return INTENT_IRRELEVANT
    return INTENT_JKLU

