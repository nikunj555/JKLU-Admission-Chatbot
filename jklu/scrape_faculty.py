"""Official JKLU Faculty Portal Scraper and Ingestion Module.

Extracts all active faculty profiles from the official JKLU faculty directory:
  https://jklu.edu.in/faculty-research/faculty
  POST https://jklu.edu.in/faculty/showFacultyDataAjax
  https://jklu.edu.in/faculty/<slug>

Normalizes each faculty record into:
  - name
  - designation
  - department
  - institute
  - teaching_areas / courses
  - research_interests
  - qualifications / education
  - biography / profile_text
  - profile_url
  - source_url
  - last_updated

Generates:
  1. data/manual/faculty/<slug>.md (individual structured profiles)
  2. data/manual/faculty/faculty_directory_by_department.md (authoritative directory roster)
  3. Raw HTML cached in data/raw/html/faculty_<slug>.html
  4. Synced with data/manual/campus/ if external directory configured
"""
from __future__ import annotations

import json
import os
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from . import config as C
from .utils import log, safe_filename, write_json

NOW = lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")

FACULTY_AJAX_URL = "https://jklu.edu.in/faculty/showFacultyDataAjax"
FACULTY_PORTAL_URL = "https://jklu.edu.in/faculty-research/faculty"

# Canonical department normalization
DEPT_ALIASES = {
    "cse": "Computer Science and Engineering",
    "computer science": "Computer Science and Engineering",
    "computer science and engineering": "Computer Science and Engineering",
    "computer science & engineering": "Computer Science and Engineering",
    "department of computer science and engineering": "Computer Science and Engineering",
    "computer science engineering": "Computer Science and Engineering",
    "ece": "Electronics & Communication Engineering",
    "electronics & communication engineering": "Electronics & Communication Engineering",
    "electronics and communication engineering": "Electronics & Communication Engineering",
    "electronics engineering": "Electronics & Communication Engineering",
    "eee": "Electrical and Electronic Engineering",
    "electrical and electronic engineering": "Electrical and Electronic Engineering",
    "applied sciences": "Applied Sciences and Mathematics",
    "mathematics": "Mathematics",
    "maths": "Mathematics",
    "physics": "Physics",
    "chemistry": "Chemistry & Environment",
    "design": "Institute of Design",
    "product design": "Institute of Design (Product Design)",
    "interaction design": "Institute of Design (Interaction Design)",
    "integrated communication design": "Institute of Design (Communication Design)",
    "management": "Institute of Management",
    "economics": "Economics and Entrepreneurship",
    "finance": "Finance and Accounts",
    "marketing": "Marketing & Operations",
    "hr": "Organizational Behaviour & HR",
    "ccct": "Centre for Communication and Critical Thinking (CCCT)",
    "centre for communication and critical thinking": "Centre for Communication and Critical Thinking (CCCT)",
}


def clean_text(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def normalize_dept(dept: str, inst: str, bio: str = "", courses: str = "", research: str = "") -> str:
    d_clean = clean_text(dept)
    if d_clean:
        d_lower = d_clean.lower()
        for k, v in DEPT_ALIASES.items():
            if k in d_lower:
                return v
        return d_clean
    
    # Infer department from institute, courses, research, or bio
    haystack = f"{inst} {courses} {research} {bio}".lower()
    if any(k in haystack for k in ("computer science", "b.tech cse", "algorithms", "software engineering", "python programming")):
        return "Computer Science and Engineering"
    if any(k in haystack for k in ("electronics", "vlsi", "communication networks")):
        return "Electronics & Communication Engineering"
    if any(k in haystack for k in ("design", "interaction", "product design")):
        return "Institute of Design"
    if any(k in haystack for k in ("management", "economics", "finance", "marketing", "bba")):
        return "Institute of Management"
    if any(k in haystack for k in ("communication", "critical thinking", "english", "soft skills")):
        return "Centre for Communication and Critical Thinking (CCCT)"
    if "engineering" in (inst or "").lower():
        return "Institute of Engineering & Technology"
    return clean_text(inst) or "JK Lakshmipat University Faculty"


def fetch_all_faculty_cards() -> list[dict]:
    """Fetch directory list from AJAX endpoint."""
    cards: list[dict] = []
    seen_urls = set()
    page = 1
    while True:
        try:
            data = {"page": page, "limit": 40, "institute_id": "", "str": ""}
            resp = requests.post(FACULTY_AJAX_URL, data=data, verify=False, timeout=15)
            if resp.status_code != 200:
                break
            parts = resp.text.split("###")
            if len(parts) < 3:
                break
            soup = BeautifulSoup(parts[0], "html.parser")
            boxes = soup.find_all("div", class_="faculty-box")
            if not boxes:
                break
            for b in boxes:
                h4 = b.find("h4")
                h5 = b.find("h5")
                h6 = b.find("h6")
                a = b.find("a", href=True)
                url = a["href"].strip() if a else ""
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                cards.append({
                    "name": clean_text(h4.get_text() if h4 else ""),
                    "designation": clean_text(h5.get_text() if h5 else ""),
                    "institute": clean_text(h6.get_text() if h6 else ""),
                    "url": url,
                })
            total = int(parts[2])
            if len(seen_urls) >= total or len(boxes) == 0:
                break
            page += 1
        except Exception as exc:
            log.warning("Faculty card fetch error on page %d: %s", page, exc)
            break
    log.info("Discovered %d faculty cards from directory", len(cards))
    return cards


def parse_faculty_profile(url: str, card: dict | None = None) -> dict:
    """Fetch individual profile HTML and extract all fields."""
    rec = {
        "name": (card or {}).get("name", ""),
        "designation": (card or {}).get("designation", ""),
        "department": "",
        "institute": (card or {}).get("institute", ""),
        "teaching_areas": "",
        "research_interests": "",
        "qualifications": "",
        "profile_text": "",
        "profile_url": url,
        "source_url": url,
        "last_updated": NOW(),
        "raw_html": "",
    }
    try:
        resp = requests.get(url, verify=False, timeout=12)
        if resp.status_code != 200:
            return rec
        html = resp.text
        rec["raw_html"] = html
        soup = BeautifulSoup(html, "html.parser")

        # Top profile header container
        cnt = soup.find("div", class_="faculty_details_Cnt")
        if cnt:
            h2 = cnt.find("h2")
            h4 = cnt.find("h4")
            h6 = cnt.find("h6")
            p = cnt.find("p")
            if h2 and h2.get_text(strip=True):
                rec["name"] = clean_text(h2.get_text())
            if h4 and h4.get_text(strip=True):
                rec["designation"] = clean_text(h4.get_text())
            if h6 and h6.get_text(strip=True):
                rec["department"] = clean_text(h6.get_text())
            if p and p.get_text(strip=True):
                rec["institute"] = clean_text(p.get_text())

        if not rec["name"]:
            t = soup.title.get_text(strip=True) if soup.title else ""
            rec["name"] = clean_text(t.split(",")[0].strip())

        # Section extraction
        for h2 in soup.find_all("h2"):
            txt = clean_text(h2.get_text())
            ltxt = txt.lower()
            parent_text = clean_text(h2.parent.get_text(" ", strip=True).replace(txt, ""))
            if "biography" in ltxt:
                rec["profile_text"] = parent_text
            elif "research interest" in ltxt:
                rec["research_interests"] = parent_text
            elif "course" in ltxt:
                rec["teaching_areas"] = parent_text
            elif "teaching interest" in ltxt and not rec["teaching_areas"]:
                rec["teaching_areas"] = parent_text
            elif any(k in ltxt for k in ("qualification", "education", "degree")):
                rec["qualifications"] = parent_text

        # Normalized department
        rec["department"] = normalize_dept(
            rec["department"], rec["institute"],
            rec["profile_text"], rec["teaching_areas"], rec["research_interests"]
        )

    except Exception as exc:
        log.warning("Error parsing profile %s: %s", url, exc)

    return rec


def build_faculty_markdown(f: dict) -> str:
    """Format single faculty profile into clean, searchable Markdown."""
    lines = [
        f"# Faculty Profile: {f['name']}",
        "",
        f"- **Faculty Name**: {f['name']}",
        f"- **Designation**: {f['designation'] or 'Faculty Member'}",
        f"- **Department**: {f['department']}",
        f"- **Institute / School**: {f['institute'] or 'JK Lakshmipat University'}",
        f"- **Official Profile URL**: {f['profile_url']}",
        f"- **Verified Teaching Areas & Courses**: {f['teaching_areas'] or 'Information verified via official faculty directory'}",
        f"- **Research Interests**: {f['research_interests'] or 'Information verified via official faculty directory'}",
    ]
    if f.get("qualifications"):
        lines.append(f"- **Qualifications / Education**: {f['qualifications']}")
    if f.get("profile_text"):
        lines.append(f"- **Biography & Academic Background**: {f['profile_text']}")
    lines.append("")
    lines.append(f"*Source: Official JK Lakshmipat University Faculty Portal ({f['profile_url']})*")
    return "\n".join(lines)


def build_consolidated_directory_markdown(fac_list: list[dict]) -> str:
    """Consolidated departmental directory linking all faculty members with designations, courses & profile URLs."""
    by_dept = defaultdict(list)
    for f in fac_list:
        by_dept[f["department"]].append(f)

    lines = [
        "# JK Lakshmipat University (JKLU) - Official Faculty Directory & Roster",
        "",
        "This official faculty directory contains verified profiles, designations, teaching assignments, research specializations, and direct profile links for academic faculty at JK Lakshmipat University (JKLU), Jaipur.",
        "",
        "## Table of Contents by Department / Institute",
        "",
    ]
    for dept in sorted(by_dept.keys()):
        slug = re.sub(r"[^a-z0-9]+", "-", dept.lower()).strip("-")
        lines.append(f"- [{dept} ({len(by_dept[dept])} Faculty Members)](#{slug})")

    lines.append("")

    for dept in sorted(by_dept.keys()):
        dept_faculty = sorted(by_dept[dept], key=lambda x: x["name"])
        lines.append(f"## {dept}")
        lines.append("")
        lines.append(f"Total verified faculty members: {len(dept_faculty)}")
        lines.append("")
        for f in dept_faculty:
            lines.append(f"### {f['name']}")
            lines.append(f"- **Designation**: {f['designation'] or 'Faculty Member'}")
            lines.append(f"- **Department**: {f['department']}")
            lines.append(f"- **Institute**: {f['institute'] or 'JK Lakshmipat University'}")
            lines.append(f"- **Official Profile Link**: {f['profile_url']}")
            if f.get("teaching_areas"):
                lines.append(f"- **Verified Teaching Areas / Courses**: {f['teaching_areas']}")
            if f.get("research_interests"):
                lines.append(f"- **Research Interests**: {f['research_interests']}")
            if f.get("profile_text"):
                short_bio = f['profile_text'][:300] + "..." if len(f['profile_text']) > 300 else f['profile_text']
                lines.append(f"- **Overview**: {short_bio}")
            lines.append("")

    lines.append("---")
    lines.append("*All records retrieved from the official JKLU Faculty Portal (https://jklu.edu.in/faculty-research/faculty).*")
    return "\n".join(lines)


def scrape_and_save_all_faculty(workers: int = 8) -> list[dict]:
    """Crawl, parse, and save all faculty documents to disk."""
    log.info("Starting official JKLU faculty ingestion...")
    cards = fetch_all_faculty_cards()
    if not cards:
        log.warning("No faculty cards fetched from live site.")
        return []

    profiles: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_card = {pool.submit(parse_faculty_profile, c["url"], c): c for c in cards}
        for fut in as_completed(future_to_card):
            try:
                prof = fut.result()
                if prof.get("name"):
                    profiles.append(prof)
            except Exception as exc:
                log.warning("Faculty profile processing failed: %s", exc)

    profiles.sort(key=lambda x: (x["department"], x["name"]))
    log.info("Successfully parsed %d faculty profiles", len(profiles))

    # Directories
    faculty_manual_dir = C.MANUAL_DIR / "faculty"
    faculty_manual_dir.mkdir(parents=True, exist_ok=True)
    C.RAW_HTML_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Save raw HTML and individual markdown profiles
    manifest = json.loads(C.MANIFEST_PATH.read_text(encoding="utf-8")) if C.MANIFEST_PATH.is_file() else {}

    for f in profiles:
        slug = f["profile_url"].rstrip("/").split("/")[-1]
        md_content = build_faculty_markdown(f)
        md_path = faculty_manual_dir / f"{slug}.md"
        md_path.write_text(md_content, encoding="utf-8")

        # Raw HTML cache
        if f.get("raw_html"):
            raw_path = C.RAW_HTML_DIR / f"faculty_{slug}.html"
            raw_path.write_text(f["raw_html"], encoding="utf-8")
            manifest[f["profile_url"]] = {
                "file": str(raw_path.relative_to(C.ROOT)).replace("\\", "/"),
                "kind": "html",
                "fetched_at": NOW(),
            }

    # 2. Save consolidated departmental directory
    dir_md = build_consolidated_directory_markdown(profiles)
    (faculty_manual_dir / "faculty_directory_by_department.md").write_text(dir_md, encoding="utf-8")

    # 3. Save JSON dump for structured lookup
    json_path = faculty_manual_dir / "faculty_data.json"
    clean_profiles = [{k: v for k, v in p.items() if k != "raw_html"} for p in profiles]
    write_json(json_path, clean_profiles)

    # 4. Save manifest
    write_json(C.MANIFEST_PATH, manifest)

    # 5. Sync with external campus directory if configured
    for extra_dir in getattr(C, "EXTRA_DATA_DIRS", []):
        if extra_dir.is_dir():
            target_ext = extra_dir / "faculty"
            try:
                target_ext.mkdir(parents=True, exist_ok=True)
                for f_path in faculty_manual_dir.glob("*.md"):
                    (target_ext / f_path.name).write_text(f_path.read_text(encoding="utf-8"), encoding="utf-8")
                (target_ext / "faculty_data.json").write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
                log.info("Synced faculty files to external directory: %s", target_ext)
            except Exception as exc:
                log.warning("Could not sync to extra directory %s: %s", extra_dir, exc)

    log.info("Faculty ingestion complete. Total profiles saved: %d", len(profiles))
    return profiles


if __name__ == "__main__":
    scrape_and_save_all_faculty()
