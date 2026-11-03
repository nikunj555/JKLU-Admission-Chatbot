"""Build Structured Faculty Index for JKLU.

Scans data/processed/chunks.jsonl and data/manual/faculty/ for every faculty record,
extracting deterministic fields (name, designation, department, school, programmes,
qualification, experience, email, profile_url, chunk_id), deduping by normalized name,
and mapping to canonical departments/schools via data/manual/faculty_aliases.json.

Saves output to data/processed/faculty.json.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MANUAL_DIR = ROOT / "data" / "manual" / "faculty"
CHUNKS_FILE = ROOT / "data" / "processed" / "chunks.jsonl"
ALIASES_FILE = ROOT / "data" / "manual" / "faculty_aliases.json"
OUTPUT_FILE = ROOT / "data" / "processed" / "faculty.json"

def normalize_name(name: str) -> str:
    """Strip Dr./Prof./Mr./Ms. prefixes and normalize spacing for robust deduplication."""
    n = re.sub(r"^(?:dr\.?|prof\.?|mr\.?|ms\.?|mrs\.?)\s+", "", name.strip(), flags=re.I)
    n = re.sub(r"\s+", " ", n).strip().lower()
    return n

def compute_seniority_rank(designation: str) -> int:
    """Return seniority sort key: lower is more senior."""
    d = (designation or "").lower()
    if any(w in d for w in ("vice chancellor", "director", "dean", "head of department", "hod")):
        return 1
    if "associate professor" in d:
        return 3
    if "assistant professor" in d:
        return 4
    if any(w in d for w in ("professor", "professor of practice")):
        return 2
    return 5

def canonicalize_dept(raw_dept: str, raw_school: str, aliases: dict) -> tuple[str, str]:
    """Map raw department and institute to canonical department and school."""
    dept_map = aliases.get("departments", {})
    school_map = aliases.get("schools", {})
    
    text = f"{raw_dept} {raw_school}".lower()
    
    # 1. Match Department
    canonical_dept = raw_dept.strip()
    for c_dept, alias_list in dept_map.items():
        if any(re.search(rf"\b{re.escape(a)}\b", text) for a in alias_list):
            canonical_dept = c_dept
            break
            
    # 2. Match School / Institute
    canonical_school = raw_school.strip() if raw_school else "Institute of Engineering & Technology"
    if canonical_dept in ("Computer Science and Engineering", "Electronics & Communication Engineering", 
                          "Electrical and Electronic Engineering", "Mathematics", "Chemistry & Environment",
                          "Centre for Communication and Critical Thinking (CCCT)"):
        canonical_school = "Institute of Engineering & Technology"
    elif canonical_dept == "Management":
        canonical_school = "Institute of Management"
    elif canonical_dept == "Design":
        canonical_school = "Institute of Design"
    else:
        for c_school, alias_list in school_map.items():
            if any(re.search(rf"\b{re.escape(a)}\b", text) for a in alias_list):
                canonical_school = c_school
                break
                
    return canonical_dept, canonical_school

def extract_qualifications(bio_text: str) -> str:
    """Deterministic regex extraction of degree and institution."""
    if not bio_text:
        return ""
    deg_patterns = [
        r"\b(Ph\.?D\.?(?:\s+in\s+[^,.\n;]+)?(?:\s+from\s+[^,.\n;]+)?)",
        r"\b(PostDoc(?:\s+in\s+[^,.\n;]+)?(?:\s+from\s+[^,.\n;]+)?)",
        r"\b(Doctorate(?:\s+in\s+[^,.\n;]+)?(?:\s+from\s+[^,.\n;]+)?)",
        r"\b(M\.?Tech(?:\s+in\s+[^,.\n;]+)?(?:\s+from\s+[^,.\n;]+)?)",
        r"\b(M\.?Des(?:\s+in\s+[^,.\n;]+)?(?:\s+from\s+[^,.\n;]+)?)",
        r"\b(MBA(?:\s+in\s+[^,.\n;]+)?(?:\s+from\s+[^,.\n;]+)?)",
        r"\b(B\.?Tech(?:\s+in\s+[^,.\n;]+)?(?:\s+from\s+[^,.\n;]+)?)",
        r"\b(B\.?E\.?(?:\s+in\s+[^,.\n;]+)?(?:\s+from\s+[^,.\n;]+)?)",
        r"\b(M\.?Sc\.?(?:\s+in\s+[^,.\n;]+)?(?:\s+from\s+[^,.\n;]+)?)",
    ]
    matches = []
    for pat in deg_patterns:
        for m in re.finditer(pat, bio_text, re.I):
            val = m.group(1).strip()
            # Trim trailing coordinating conjunctions / pronouns
            val = re.split(r"\b(and|where|with|he|she|his|her|before|after|in\s+20\d\d)\b", val, flags=re.I)[0].strip()
            # Remove punctuation
            val = val.rstrip(" .,;")
            if len(val) >= 4 and not any(val.lower() == existing.lower() for existing in matches):
                matches.append(val)
                if len(matches) >= 2:
                    break
        if len(matches) >= 2:
            break
            
    return "; ".join(matches) if matches else ""

def build_index() -> dict:
    print("=" * 80)
    print("Building Structured Faculty Index")
    print("=" * 80)
    
    # Load aliases
    aliases = {}
    if ALIASES_FILE.is_file():
        aliases = json.loads(ALIASES_FILE.read_text(encoding="utf-8"))
        
    # 1. Collect emails and chunk IDs from chunks.jsonl
    chunk_meta: dict[str, dict] = {}
    if CHUNKS_FILE.is_file():
        with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                c = json.loads(line)
                if c.get("category") == "faculty":
                    url = c.get("source_url", "")
                    slug = ""
                    if "/faculty/" in url:
                        slug = url.split("/faculty/")[-1].split("/")[0].split(".")[0]
                    if not slug and c.get("title"):
                        slug = normalize_name(c["title"]).replace(" ", "-")
                    if slug:
                        if slug not in chunk_meta:
                            chunk_meta[slug] = {
                                "email": "",
                                "chunk_id": c.get("chunk_id", ""),
                                "source_url": url,
                                "source_title": c.get("title", ""),
                            }
                        if not chunk_meta[slug]["email"]:
                            m = re.search(r"[\w\.-]+@jklu\.edu\.in", c.get("text", ""))
                            if m:
                                chunk_meta[slug]["email"] = m.group(0)

    # 2. Parse individual Markdown profile files
    faculty_by_id: dict[str, dict] = {}
    if MANUAL_DIR.is_dir():
        for md_path in MANUAL_DIR.glob("*.md"):
            if md_path.name.startswith("faculty_directory"):
                continue
            slug = md_path.stem
            content = md_path.read_text(encoding="utf-8")
            
            fields: dict[str, str] = {}
            for line in content.splitlines():
                m = re.match(r"^-\s*\*\*([^*]+)\*\*:\s*(.*)", line.strip())
                if m:
                    fields[m.group(1).strip()] = m.group(2).strip()
                    
            name = fields.get("Faculty Name") or md_path.stem.replace("-", " ").title()
            desig = fields.get("Designation", "Faculty Member")
            raw_dept = fields.get("Department", "")
            raw_school = fields.get("Institute / School") or fields.get("Institute", "")
            profile_url = fields.get("Official Profile URL") or f"https://jklu.edu.in/faculty/{slug}"
            teaching = fields.get("Verified Teaching Areas & Courses") or fields.get("Verified Teaching Areas / Courses", "")
            research = fields.get("Research Interests", "")
            bio = fields.get("Biography & Academic Background") or fields.get("Overview", "")
            
            c_dept, c_school = canonicalize_dept(raw_dept, raw_school, aliases)
            qual = extract_qualifications(bio)
            
            meta = chunk_meta.get(slug, {})
            email = meta.get("email", "")
            chunk_id = meta.get("chunk_id", f"manual_{slug}")
            source_title = meta.get("source_title", f"Faculty Profile: {name}")
            source_url = meta.get("source_url", profile_url)
            
            # Derive programmes
            programmes = []
            if c_school == "Institute of Engineering & Technology":
                programmes.extend(["B.Tech", "M.Tech"])
            elif c_school == "Institute of Management":
                programmes.extend(["BBA", "MBA"])
            elif c_school == "Institute of Design":
                programmes.extend(["B.Des", "M.Des"])
                
            entry = {
                "id": slug,
                "name": name,
                "normalized_name": normalize_name(name),
                "designation": desig,
                "seniority_rank": compute_seniority_rank(desig),
                "department": c_dept,
                "school": c_school,
                "programmes": programmes,
                "qualification": qual,
                "teaching_areas": teaching,
                "research_interests": research,
                "biography": bio,
                "email": email,
                "profile_url": profile_url,
                "source_title": source_title,
                "source_url": source_url,
                "chunk_id": chunk_id,
            }
            faculty_by_id[slug] = entry

    # 3. Check data/manual/faculty/faculty_data.json for any missing profiles
    data_json_path = MANUAL_DIR / "faculty_data.json"
    if data_json_path.is_file():
        extra_list = json.loads(data_json_path.read_text(encoding="utf-8"))
        for item in extra_list:
            name = item.get("name", "")
            norm = normalize_name(name)
            slug = norm.replace(" ", "-")
            if slug not in faculty_by_id and not any(normalize_name(f["name"]) == norm for f in faculty_by_id.values()):
                desig = item.get("designation", "Faculty Member")
                c_dept, c_school = canonicalize_dept(item.get("department", ""), item.get("institute", ""), aliases)
                bio = item.get("profile_text", "")
                qual = item.get("qualifications") or extract_qualifications(bio)
                meta = chunk_meta.get(slug, {})
                
                entry = {
                    "id": slug,
                    "name": name,
                    "normalized_name": norm,
                    "designation": desig,
                    "seniority_rank": compute_seniority_rank(desig),
                    "department": c_dept,
                    "school": c_school,
                    "programmes": ["B.Tech", "M.Tech"] if "Engineering" in c_school else (["BBA", "MBA"] if "Management" in c_school else ["B.Des"]),
                    "qualification": qual,
                    "teaching_areas": item.get("teaching_areas", ""),
                    "research_interests": item.get("research_interests", ""),
                    "biography": bio,
                    "email": meta.get("email", ""),
                    "profile_url": item.get("profile_url", f"https://jklu.edu.in/faculty/{slug}"),
                    "source_title": f"Faculty Profile: {name}",
                    "source_url": item.get("source_url", f"https://jklu.edu.in/faculty/{slug}"),
                    "chunk_id": meta.get("chunk_id", f"manual_{slug}"),
                }
                faculty_by_id[slug] = entry

    # 4. Group by Department & Sort by Seniority
    all_faculty = list(faculty_by_id.values())
    by_department: dict[str, list[dict]] = {}
    for f in all_faculty:
        dept = f["department"]
        by_department.setdefault(dept, []).append(f)
        
    for dept, members in by_department.items():
        members.sort(key=lambda m: (m["seniority_rank"], m["normalized_name"]))

    by_school: dict[str, list[dict]] = {}
    for f in all_faculty:
        sch = f["school"]
        by_school.setdefault(sch, []).append(f)
        
    for sch, members in by_school.items():
        members.sort(key=lambda m: (m["seniority_rank"], m["normalized_name"]))

    index_data = {
        "total_faculty": len(all_faculty),
        "departments": list(by_department.keys()),
        "schools": list(by_school.keys()),
        "by_department": by_department,
        "by_school": by_school,
        "faculty_list": all_faculty,
        "by_id": faculty_by_id,
        "by_normalized_name": {f["normalized_name"]: f for f in all_faculty},
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(index_data, indent=2, ensure_ascii=False), encoding="utf-8")
    file_size_kb = OUTPUT_FILE.stat().st_size / 1024
    
    print(f"\nSaved structured faculty index to {OUTPUT_FILE} ({file_size_kb:.1f} KB)")
    print(f"Total Verified Faculty Indexed: {len(all_faculty)}")
    
    print("\nFaculty Count per Department:")
    for dept, members in sorted(by_department.items(), key=lambda x: -len(x[1])):
        print(f"  - {dept:<50}: {len(members):2d} faculty")
        
    print("\nFaculty Count per School / Institute:")
    for sch, members in sorted(by_school.items(), key=lambda x: -len(x[1])):
        print(f"  - {sch:<50}: {len(members):2d} faculty")
        
    # Missing fields report
    missing_email = [f["name"] for f in all_faculty if not f["email"]]
    missing_qual = [f["name"] for f in all_faculty if not f["qualification"]]
    
    print("\nMissing Fields Report:")
    print(f"  - Missing Email: {len(missing_email)} records")
    if missing_email:
        print(f"    ({', '.join(missing_email[:5])}{', ...' if len(missing_email) > 5 else ''})")
    print(f"  - Missing Qualification: {len(missing_qual)} records")
    if missing_qual:
        print(f"    ({', '.join(missing_qual[:5])}{', ...' if len(missing_qual) > 5 else ''})")
    print("=" * 80)
    
    return index_data

if __name__ == "__main__":
    build_index()

