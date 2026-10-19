"""Curated JKLU source list, URL->category classification and crawl rules.

Seeds were verified against the live site. A seed may contain several
`candidates` (alternative URLs for the same document, e.g. the yearly Hostel
Life Policy PDF whose file name changes every year): the first candidate that
downloads successfully is used.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import unquote, urldefrag, urlparse

B = "https://jklu.edu.in"


@dataclass
class Seed:
    category: str
    candidates: list[str]
    title: str = ""
    priority: int = 2            # 3 = core source, 1 = supplementary
    kind: str = "auto"           # auto | html | pdf
    meta: dict = field(default_factory=dict)


SEEDS: list[Seed] = [
    # ------------------------------------------------------------ admission
    Seed("admission", [f"{B}/admissions/eligibility", f"{B}/eligibility"], "Admission Eligibility", 3),
    Seed("admission", [f"{B}/admissions/application-process"], "Application Process", 3),
    Seed("admission", [f"{B}/admissions/entrance-exams"], "Entrance Exams", 3),
    Seed("admission", [f"{B}/admissions/lateral-entry"], "Lateral Entry", 2),
    Seed("admission", [f"{B}/admissions/international-admissions"], "International Admissions", 2),
    Seed("admission", [f"{B}/admissions/brochures"], "Brochures & Admission Documents", 2),
    Seed("admission", [f"{B}/uploads/images/Withdrawal Application Form_2026.pdf"],
         "Application Withdrawal Form 2026", 2),
    # ----------------------------------------------------------------- fees
    Seed("fees", [f"{B}/admissions/fee-structure"], "Fee Structure", 3),
    Seed("fees", [f"{B}/uploads/images/Fee_Refund_Policy_2026.pdf"], "Fee Refund Policy 2026", 3),
    # --------------------------------------------------------- scholarships
    Seed("scholarships", [f"{B}/admissions/scholarship-aid"], "Scholarship & Aid", 3),
    # --------------------------------------------------------------- hostel
    Seed("hostel", [
        f"{B}/uploads/images/Hostel-Life-Policy-JKLU-AY-2026-2027.pdf",
        f"{B}/uploads/images/Hostel_Life_Policy_JKLU_AY_2026-2027.pdf",
        f"{B}/uploads/images/Hostel _Life_Policy_2026-27.pdf",
        f"{B}/uploads/images/Hostel Life Policy JKLU AY 2025-2026.pdf",
        f"{B}/pdf/hostel-policy.pdf",
    ], "Hostel Life Policy", 3, "pdf"),
    # ------------------------------------------------------------- academics
    Seed("academics", [f"{B}/programmes"], "All Programmes", 3),
    Seed("academics", [f"{B}/programme/btech"], "B.Tech Programme", 3),
    Seed("academics", [f"{B}/programme/bdes"], "B.Des Programme", 2),
    Seed("academics", [f"{B}/programme/bba"], "BBA Programme", 2),
    Seed("academics", [f"{B}/programme/mtech"], "M.Tech Programme", 2),
    Seed("academics", [f"{B}/programme/mdes"], "M.Des Programme", 2),
    Seed("academics", [f"{B}/programme/phd"], "PhD Programme", 2),
    Seed("academics", [f"{B}/institute/engineering-technology"], "Institute of Engineering & Technology", 2),
    Seed("academics", [f"{B}/institute/design"], "Institute of Design", 2),
    Seed("academics", [f"{B}/institute/management"], "Institute of Management", 2),
    Seed("academics", [f"{B}/academics/academic-regulations"], "Academic Policies & Regulations", 3),
    Seed("academics", [f"{B}/academics/academic-calander", f"{B}/academics/academic-calendar"],
         "Academic Calendars", 3),
    Seed("academics", [f"{B}/academics/collaborations"], "Collaborations", 1),
    Seed("academics", [f"{B}/academics/innovative-pedagogy"], "Innovative Pedagogy", 1),
    Seed("academics", [f"{B}/uploads/pdf/university-prospectus.pdf"], "University Prospectus", 2),
    Seed("academics", [f"{B}/uploads/course/pdf/Engineering-JKLU-New-Brochure-March2025-V9 (2).pdf"],
         "Engineering Brochure 2025", 2),
    Seed("academics", [f"{B}/uploads/course/pdf/btech-cse-2023-2027.pdf"], "B.Tech CSE Curriculum 2023-27", 1),
    Seed("academics", [f"{B}/uploads/course/pdf/btech-in-cse_ai-2023-2027.pdf"],
         "B.Tech CSE (AI) Curriculum 2023-27", 1),
    Seed("academics", [f"{B}/pdf/handbook-phd-coursework-ay-2024-25.pdf"], "PhD Coursework Handbook 2024-25", 1),
    Seed("academics", [f"{B}/pdf/institute-of-ingineering-and-technology-2025-2026.pdf"],
         "Institute of Engineering & Technology Handbook 2025-26", 1),
    # ----------------------------------------------------------- examination
    Seed("examination", [f"{B}/siteassets/pdf/revised-guidelines-for-the-award-of-grades.pdf"],
         "Revised Guidelines for the Award of Grades", 3),
    Seed("examination", [f"{B}/siteassets/pdf/guidelines-for-the-award-of-grades.pdf"],
         "Guidelines for the Award of Grades", 2),
    Seed("examination", [
        f"{B}/siteassets/pdf/rules-for-Identification-and-classification-of-academically-deficient-students.pdf"],
        "Rules for Identification and Classification of Academically Deficient Students", 3),
    Seed("examination", [f"{B}/siteassets/pdf/change-in-rules.pdf"], "Change in Rules", 2),
    Seed("examination", ["https://naac.jklu.edu.in/wp-content/uploads/2021/06/JKLU_Regulations.pdf"],
         "JKLU Regulations (examination, grading, attendance)", 2),
    # ----------------------------------------------------------------- faculty
    Seed("faculty", [f"{B}/institute/engineering-technology/faculty"], "Engineering & Technology Faculty", 3),
    Seed("faculty", [f"{B}/institute/design/faculty"], "Design Faculty", 3),
    Seed("faculty", [f"{B}/institute/management/faculty"], "Management Faculty", 3),
    Seed("faculty", [f"{B}/faculty"], "JKLU Faculty Directory", 3),
    # --------------------------------------------------------------- contact
    Seed("contact", [f"{B}/contact-us"], "Contact Us", 3),
    # --------------------------------------------------------------- campus / general
    Seed("general", [f"{B}/campus-life"], "Campus Life", 2),
    Seed("general", [f"{B}/student-life"], "Student Life", 2),
    Seed("general", [f"{B}/about-us"], "About JKLU", 2),
    Seed("general", [f"{B}/about-us/vision-mission"], "Vision & Mission", 1),
    Seed("general", [f"{B}/about-us/leadership-governance"], "Leadership & Governance", 1),
    Seed("general", [f"{B}/placements", f"{B}/placement"], "Placements", 2),
    Seed("general", [f"{B}/centres", f"{B}/center"], "Research Centers", 1),
    Seed("general", [B], "JKLU Home", 1),
    # --------------------------------------------------------------- notices
    Seed("notices", [f"{B}/announcements"], "Announcements", 2),
    Seed("notices", [f"{B}/newsroom"], "Newsroom", 1),
]

# --------------------------------------------------------------------------
# Crawl policy for *discovered* links (seeds are always fetched).
# --------------------------------------------------------------------------
ALLOWED_HOST_SUFFIX = "jklu.edu.in"
BLOCKED_HOSTS = {"applications.jklu.edu.in", "alumni.jklu.edu.in", "mail.jklu.edu.in"}

FOLLOW_PATH_PREFIXES = (
    "/admissions", "/eligibility", "/academics", "/programme", "/programmes", "/institute",
    "/centres", "/about-us", "/policies", "/policy", "/campus-life", "/student-life", "/hostel",
    "/contact-us", "/announcements", "/newsroom", "/scholarship", "/fee",
    "/placements", "/placement", "/about", "/center", "/faculty",
)
DENY_PATH_FRAGMENTS = (
    "/blog", "/events", "/event/", "/gallery", "/tag/", "/category/", "/feed",
    "/wp-json", "/cdn-cgi", "/search", "/login", "/careers", "/press-release",
)
DENY_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".mp4", ".mp3", ".zip", ".rar",
    ".css", ".js", ".xml", ".json", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".woff", ".woff2",
)


def canonicalize(url: str) -> str | None:
    """Normalise a URL (drop fragment/query tracking, trailing slash)."""
    if not url:
        return None
    url = url.strip()
    url, _ = urldefrag(url)
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        return None
    host = p.hostname.lower()
    path = p.path or ""
    if len(path) > 1:
        path = path.rstrip("/")
    query = ""
    if p.query and not re.search(r"utm_|fbclid|gclid", p.query, re.I):
        query = "?" + p.query
    if path in ("", "/"):
        path = ""
    port = f":{p.port}" if p.port and p.port not in (80, 443) else ""
    return f"{p.scheme}://{host}{port}{path}{query}"


def is_allowed_host(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if host in BLOCKED_HOSTS:
        return False
    return host == ALLOWED_HOST_SUFFIX or host.endswith("." + ALLOWED_HOST_SUFFIX)


def is_pdf_url(url: str) -> bool:
    return urlparse(url).path.lower().endswith(".pdf")


def should_follow(url: str) -> bool:
    """Whether a *discovered* link is worth fetching."""
    if not url or not is_allowed_host(url):
        return False
    p = urlparse(url)
    path = unquote(p.path).lower()
    if is_pdf_url(url):
        return not any(f in path for f in DENY_PATH_FRAGMENTS)
    if path.endswith(DENY_EXTENSIONS):
        return False
    if any(f in path for f in DENY_PATH_FRAGMENTS):
        return False
    if p.hostname and p.hostname.lower().startswith("naac."):
        return False  # only specific NAAC PDFs are seeded
    return path == "" or path.startswith(FOLLOW_PATH_PREFIXES)


# --------------------------------------------------------------------------
# Category classification (ordered: first matching rule wins)
# --------------------------------------------------------------------------
_RULES: list[tuple[str, re.Pattern]] = [
    ("hostel", re.compile(r"hostel|mess\b|residen|accommodation", re.I)),
    ("scholarships", re.compile(r"scholarship|financial[-_ ]aid|\baid\b|stipend", re.I)),
    ("fees", re.compile(r"\bfees?\b|fee[-_ ]|refund|tuition|payment", re.I)),
    ("admission", re.compile(r"entrance|eligib|lateral|international[-_ ]admission", re.I)),
    ("examination", re.compile(
        r"exam|grading|grades?\b|award[-_ ]of[-_ ]grades|academically[-_ ]deficient|"
        r"change[-_ ]in[-_ ]rules|regulations\.pdf|assessment|attendance", re.I)),
    ("notices", re.compile(r"announcement|notice|newsroom|circular", re.I)),
    ("contact", re.compile(r"contact", re.I)),
    ("faculty", re.compile(r"faculty|professor|dean\b|director|ph\.?d\.?[-_ ]guides|lecturer|instructor|educator", re.I)),
    ("admission", re.compile(
        r"admission|eligib|application|entrance|apply|lateral|international|withdraw|brochure", re.I)),
    ("academics", re.compile(
        r"academic|programme|program\b|course|curricul|syllabus|institute|centre|department|"
        r"handbook|prospectus|calendar|calander|regulation", re.I)),
    ("general", re.compile(r"about|vision|mission|leadership|governance|campus", re.I)),
]


def classify(url: str, anchor: str = "", fallback: str = "general") -> str:
    """Classify a URL (and optional link text) into one of the categories."""
    p = urlparse(url)
    if p.path in ("", "/") and not anchor:
        return "general"
    haystack = unquote(f"{p.path} {anchor}")
    for cat, rx in _RULES:
        if rx.search(haystack):
            return cat
    return fallback


def title_from_url(url: str) -> str:
    name = unquote(urlparse(url).path.rsplit("/", 1)[-1])
    name = re.sub(r"\.(pdf|html?)$", "", name, flags=re.I)
    name = re.sub(r"[-_]+", " ", name).strip()
    return name.title() if name else url
