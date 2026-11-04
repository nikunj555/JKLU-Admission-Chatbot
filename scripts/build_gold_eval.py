#!/usr/bin/env python3
"""Build the comprehensive gold evaluation dataset for JKLU Assistant.

Generates data/eval/gold.jsonl with 90 realistic student questions.
All expected facts and sources are strictly derived from data/processed/chunks.jsonl
and data/manual documents.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = ROOT / "data" / "eval"
EVAL_DIR.mkdir(parents=True, exist_ok=True)
GOLD_PATH = EVAL_DIR / "gold.jsonl"

GOLD_QUESTIONS = [
    # =========================================================================
    # 1. FEES (12 questions)
    # =========================================================================
    {
        "id": "fee_01",
        "category": "fees",
        "question": "What is the annual academic fee for B.Tech in 2026-27?",
        "expected_facts": ["2,84,000", "B.Tech"],
        "expected_source": "Fee Structure",
        "answerable": True,
    },
    {
        "id": "fee_02",
        "category": "fees",
        "question": "How much is the tuition fee for the Bachelor of Design (B.Des) programme?",
        "expected_facts": ["3,05,000"],
        "expected_source": "Fee Structure",
        "answerable": True,
    },
    {
        "id": "fee_03",
        "category": "fees",
        "question": "What is the annual tuition fee for the BBA programme?",
        "expected_facts": ["1,80,000"],
        "expected_source": "Fee Structure",
        "answerable": True,
    },
    {
        "id": "fee_04",
        "category": "fees",
        "question": "What is the annual academic fee for the M.Tech programme?",
        "expected_facts": ["1,80,000"],
        "expected_source": "Fee Structure",
        "answerable": True,
    },
    {
        "id": "fee_05",
        "category": "fees",
        "question": "What is the part-time PhD fee at JKLU?",
        "expected_facts": ["55,000"],
        "expected_source": "Fee Structure",
        "answerable": True,
    },
    {
        "id": "fee_06",
        "category": "fees",
        "question": "What is the one-time admission fee for new students?",
        "expected_facts": ["12,000", "admission fee"],
        "expected_source": "Fee Structure",
        "answerable": True,
    },
    {
        "id": "fee_07",
        "category": "fees",
        "question": "What is the refundable caution deposit for B.Tech admissions?",
        "expected_facts": ["10,000", "caution"],
        "expected_source": "Fee Structure",
        "answerable": True,
    },
    {
        "id": "fee_08",
        "category": "fees",
        "question": "How much is the additional KPMG specialization fee for BBA if opted?",
        "expected_facts": ["40,000", "KPMG"],
        "expected_source": "Fee Structure",
        "answerable": True,
    },
    {
        "id": "fee_09",
        "category": "fees",
        "question": "What is the fee refund policy if a student withdraws before the academic session starts?",
        "expected_facts": ["100%", "refund"],
        "expected_source": "Fee Refund Policy",
        "answerable": True,
    },
    {
        "id": "fee_10",
        "category": "fees",
        "question": "Where can students obtain the official admission withdrawal application form?",
        "expected_facts": ["Withdrawal Application Form", "admissions"],
        "expected_source": "Withdrawal",
        "answerable": True,
    },
    {
        "id": "fee_11",
        "category": "fees",
        "question": "What is the one-time application fee for submitting the admission form?",
        "expected_facts": ["1,000", "application fee"],
        "expected_source": "Admission",
        "answerable": True,
    },
    {
        "id": "fee_12",
        "category": "fees",
        "question": "Is the caution money deposit refundable upon graduation?",
        "expected_facts": ["refundable", "caution deposit"],
        "expected_source": "Fee Structure",
        "answerable": True,
    },

    # =========================================================================
    # 2. ELIGIBILITY & CUT-OFFS (10 questions)
    # =========================================================================
    {
        "id": "elig_01",
        "category": "eligibility",
        "question": "What is the minimum Class XII percentage required for B.Tech admission?",
        "expected_facts": ["60%", "Physics", "Mathematics"],
        "expected_source": "Admission",
        "answerable": True,
    },
    {
        "id": "elig_02",
        "category": "eligibility",
        "question": "What are the eligibility criteria for admission into Bachelor of Design (B.Des)?",
        "expected_facts": ["60%", "10+2"],
        "expected_source": "Admission",
        "answerable": True,
    },
    {
        "id": "elig_03",
        "category": "eligibility",
        "question": "What is the minimum percentage required in Class 12 for BBA admission?",
        "expected_facts": ["60%", "10+2"],
        "expected_source": "Admission",
        "answerable": True,
    },
    {
        "id": "elig_04",
        "category": "eligibility",
        "question": "Which national entrance exams are accepted for B.Tech admission at JKLU?",
        "expected_facts": ["JEE Main"],
        "expected_source": "Admission",
        "answerable": True,
    },
    {
        "id": "elig_05",
        "category": "eligibility",
        "question": "What entrance exam is conducted for Bachelor of Design admissions?",
        "expected_facts": ["DET", "Design Entrance Test"],
        "expected_source": "Admission",
        "answerable": True,
    },
    {
        "id": "elig_06",
        "category": "eligibility",
        "question": "What are the eligibility requirements for M.Tech Computer Science admission?",
        "expected_facts": ["B.Tech", "50%"],
        "expected_source": "Admission",
        "answerable": True,
    },
    {
        "id": "elig_07",
        "category": "eligibility",
        "question": "Does JKLU allow diploma holders to apply for lateral entry into B.Tech second year?",
        "expected_facts": ["lateral entry", "diploma"],
        "expected_source": "Admission",
        "answerable": True,
    },
    {
        "id": "elig_08",
        "category": "eligibility",
        "question": "Can students from any 12th stream (Arts/Science/Commerce) apply for B.Des?",
        "expected_facts": ["any stream", "recognized board"],
        "expected_source": "Admission",
        "answerable": True,
    },
    {
        "id": "elig_09",
        "category": "eligibility",
        "question": "What is the eligibility requirement for the full-time PhD programme?",
        "expected_facts": ["Master's degree", "55%"],
        "expected_source": "Admission",
        "answerable": True,
    },
    {
        "id": "elig_10",
        "category": "eligibility",
        "question": "Is mathematics compulsory in 12th for B.Tech Computer Science?",
        "expected_facts": ["Mathematics", "compulsory"],
        "expected_source": "Admission",
        "answerable": True,
    },

    # =========================================================================
    # 3. SCHOLARSHIPS (8 questions)
    # =========================================================================
    {
        "id": "sch_01",
        "category": "scholarships",
        "question": "What scholarship is awarded to B.Tech applicants with a JEE Main percentile of 95 or above?",
        "expected_facts": ["100%", "academic fee"],
        "expected_source": "Scholarship",
        "answerable": True,
    },
    {
        "id": "sch_02",
        "category": "scholarships",
        "question": "What scholarship percentage is offered for JEE Main percentile between 90 and 95?",
        "expected_facts": ["75%"],
        "expected_source": "Scholarship",
        "answerable": True,
    },
    {
        "id": "sch_03",
        "category": "scholarships",
        "question": "What scholarship waiver is available for students scoring 85 to 90 percentile in JEE Main?",
        "expected_facts": ["50%"],
        "expected_source": "Scholarship",
        "answerable": True,
    },
    {
        "id": "sch_04",
        "category": "scholarships",
        "question": "Does JKLU provide scholarships based on Class 12 board marks for B.Tech?",
        "expected_facts": ["Class XII", "scholarship"],
        "expected_source": "Scholarship",
        "answerable": True,
    },
    {
        "id": "sch_05",
        "category": "scholarships",
        "question": "What is the minimum CGPA requirement to renew the merit scholarship in subsequent years?",
        "expected_facts": ["CGPA", "renewal"],
        "expected_source": "Scholarship",
        "answerable": True,
    },
    {
        "id": "sch_06",
        "category": "scholarships",
        "question": "Can scholarships be combined or do students receive the single highest scholarship?",
        "expected_facts": ["single highest", "cannot be combined"],
        "expected_source": "Scholarship",
        "answerable": True,
    },
    {
        "id": "sch_07",
        "category": "scholarships",
        "question": "Is there any financial assistance or government scholarship program supported at JKLU?",
        "expected_facts": ["Vidya Lakshmi", "education loan"],
        "expected_source": "Scholarship",
        "answerable": True,
    },
    {
        "id": "sch_08",
        "category": "scholarships",
        "question": "What scholarship can BBA students get for high Class 12 board percentages?",
        "expected_facts": ["merit scholarship", "Class 12"],
        "expected_source": "Scholarship",
        "answerable": True,
    },

    # =========================================================================
    # 4. PLACEMENTS (10 questions)
    # =========================================================================
    {
        "id": "place_01",
        "category": "placements",
        "question": "What was the highest package (CTC) offered to B.Tech students in the 2024 batch?",
        "expected_facts": ["22.5 LPA"],
        "expected_source": "Engineering Brochure",
        "answerable": True,
    },
    {
        "id": "place_02",
        "category": "placements",
        "question": "What is the average CTC for B.Tech engineering graduates at JKLU?",
        "expected_facts": ["8.10 LPA"],
        "expected_source": "Engineering Brochure",
        "answerable": True,
    },
    {
        "id": "place_03",
        "category": "placements",
        "question": "What is the average CTC for the top 10% of placed B.Tech students?",
        "expected_facts": ["18.07 LPA"],
        "expected_source": "Engineering Brochure",
        "answerable": True,
    },
    {
        "id": "place_04",
        "category": "placements",
        "question": "Who are some of the prominent recruiters that hire from JKLU?",
        "expected_facts": ["Infosys", "TCS"],
        "expected_source": "Engineering Brochure",
        "answerable": True,
    },
    {
        "id": "place_05",
        "category": "placements",
        "question": "What is the placement percentage for registered and eligible B.Tech students?",
        "expected_facts": ["100%"],
        "expected_source": "Engineering Brochure",
        "answerable": True,
    },
    {
        "id": "place_06",
        "category": "placements",
        "question": "Does JKLU have a dedicated Career Services / Placement Cell?",
        "expected_facts": ["Career Services", "internship"],
        "expected_source": "Placement",
        "answerable": True,
    },
    {
        "id": "place_07",
        "category": "placements",
        "question": "What is the minimum attendance or eligibility criterion for students to participate in campus placements?",
        "expected_facts": ["registered", "CGPA", "placement"],
        "expected_source": "Placement",
        "answerable": True,
    },
    {
        "id": "place_08",
        "category": "placements",
        "question": "Are semester-long internships or practice schools part of the curriculum?",
        "expected_facts": ["Practice School", "internship"],
        "expected_source": "Placement",
        "answerable": True,
    },
    {
        "id": "place_09",
        "category": "placements",
        "question": "Which tech companies recruit computer science students from JKLU?",
        "expected_facts": ["IBM", "Infosys"],
        "expected_source": "Placement",
        "answerable": True,
    },
    {
        "id": "place_10",
        "category": "placements",
        "question": "What is the highest package reported across the Institute of Engineering and Technology?",
        "expected_facts": ["22.5 LPA"],
        "expected_source": "Placement",
        "answerable": True,
    },

    # =========================================================================
    # 5. FACULTY & DIRECTORY (10 questions)
    # =========================================================================
    {
        "id": "fac_01",
        "category": "faculty",
        "question": "Who are the CSE faculty at JKLU?",
        "expected_facts": ["Amit Sinhal", "Sanjay Goel"],
        "expected_source": "faculty",
        "answerable": True,
    },
    {
        "id": "fac_02",
        "category": "faculty",
        "question": "Tell me about Dr. Amit Sinhal.",
        "expected_facts": ["Associate Professor", "Computer Science"],
        "expected_source": "faculty",
        "answerable": True,
    },
    {
        "id": "fac_03",
        "category": "faculty",
        "question": "Who teaches in the Institute of Design (IoD)?",
        "expected_facts": ["Balasubramaniam", "Design"],
        "expected_source": "faculty",
        "answerable": True,
    },
    {
        "id": "fac_04",
        "category": "faculty",
        "question": "Who are the faculty members in the Management department?",
        "expected_facts": ["Management"],
        "expected_source": "faculty",
        "answerable": True,
    },
    {
        "id": "fac_05",
        "category": "faculty",
        "question": "Who is the Director of the Institute of Engineering and Technology?",
        "expected_facts": ["Director", "Engineering"],
        "expected_source": "faculty",
        "answerable": True,
    },
    {
        "id": "fac_06",
        "category": "faculty",
        "question": "Who teaches Electronics and Communication Engineering (ECE)?",
        "expected_facts": ["Electronics", "ECE"],
        "expected_source": "faculty",
        "answerable": True,
    },
    {
        "id": "fac_07",
        "category": "faculty",
        "question": "Tell me about Prof. A. Balasubramaniam.",
        "expected_facts": ["Director", "Design"],
        "expected_source": "faculty",
        "answerable": True,
    },
    {
        "id": "fac_08",
        "category": "faculty",
        "question": "Who teaches mathematics to engineering students at JKLU?",
        "expected_facts": ["Mathematics"],
        "expected_source": "faculty",
        "answerable": True,
    },
    {
        "id": "fac_09",
        "category": "faculty",
        "question": "What is the qualification and research area of Dr. Amit Sinhal?",
        "expected_facts": ["Ph.D", "Computer Science"],
        "expected_source": "faculty",
        "answerable": True,
    },
    {
        "id": "fac_10",
        "category": "faculty",
        "question": "List all faculty members in the Department of Design.",
        "expected_facts": ["Design", "Balasubramaniam"],
        "expected_source": "faculty",
        "answerable": True,
    },

    # =========================================================================
    # 6. HOSTEL & CAMPUS LIFE (10 questions)
    # =========================================================================
    {
        "id": "hostel_01",
        "category": "hostel",
        "question": "What furniture and facilities are provided inside each hostel room?",
        "expected_facts": ["bed", "wardrobe", "study table"],
        "expected_source": "Hostel Room Facilities",
        "answerable": True,
    },
    {
        "id": "hostel_02",
        "category": "hostel",
        "question": "What security arrangements are present at the hostels?",
        "expected_facts": ["24/7", "security guard"],
        "expected_source": "Hostel",
        "answerable": True,
    },
    {
        "id": "hostel_03",
        "category": "hostel",
        "question": "What dining and mess facilities are available for residential students?",
        "expected_facts": ["mess", "meals"],
        "expected_source": "Hostel",
        "answerable": True,
    },
    {
        "id": "hostel_04",
        "category": "hostel",
        "question": "Are laundry and washing facilities available on campus?",
        "expected_facts": ["laundry"],
        "expected_source": "Hostel",
        "answerable": True,
    },
    {
        "id": "hostel_05",
        "category": "hostel",
        "question": "What is the policy regarding visitors in the student hostel?",
        "expected_facts": ["visitors", "Hostel"],
        "expected_source": "Hostel Life Policy",
        "answerable": True,
    },
    {
        "id": "hostel_06",
        "category": "campus_life",
        "question": "What is Sabrang at JKLU?",
        "expected_facts": ["Sabrang", "fest"],
        "expected_source": "Calendar",
        "answerable": True,
    },
    {
        "id": "hostel_07",
        "category": "campus_life",
        "question": "What is Spardha?",
        "expected_facts": ["Spardha", "sports"],
        "expected_source": "Calendar",
        "answerable": True,
    },
    {
        "id": "hostel_08",
        "category": "campus_life",
        "question": "What is Aarambh at JKLU?",
        "expected_facts": ["Aarambh", "fest"],
        "expected_source": "Aarambh",
        "answerable": True,
    },
    {
        "id": "hostel_09",
        "category": "campus_life",
        "question": "What library facilities are available in the Learning Resource Centre (LRC)?",
        "expected_facts": ["LRC", "library", "books"],
        "expected_source": "Library Services",
        "answerable": True,
    },
    {
        "id": "hostel_10",
        "category": "campus_life",
        "question": "What medical and health facilities are available on campus for students?",
        "expected_facts": ["medical", "doctor"],
        "expected_source": "Health Medical",
        "answerable": True,
    },

    # =========================================================================
    # 7. ADMISSIONS PROCESS & DATES (8 questions)
    # =========================================================================
    {
        "id": "adm_01",
        "category": "admission",
        "question": "What are the sequential steps to apply for admission at JKLU?",
        "expected_facts": ["application", "register", "documents"],
        "expected_source": "Admission",
        "answerable": True,
    },
    {
        "id": "adm_02",
        "category": "admission",
        "question": "Which mandatory documents must be uploaded while filling the online application form?",
        "expected_facts": ["photograph", "marksheet", "Class 10"],
        "expected_source": "Admission Document Checklist",
        "answerable": True,
    },
    {
        "id": "adm_03",
        "category": "admission",
        "question": "Is an interaction or interview required as part of the B.Tech admission process?",
        "expected_facts": ["interaction", "admission"],
        "expected_source": "Admission",
        "answerable": True,
    },
    {
        "id": "adm_04",
        "category": "admission",
        "question": "How do international students apply for admission to JKLU?",
        "expected_facts": ["international", "admission"],
        "expected_source": "Admission",
        "answerable": True,
    },
    {
        "id": "adm_05",
        "category": "admission",
        "question": "When do classes typically commence for the odd semester according to the academic calendar?",
        "expected_facts": ["Commencement of Classes"],
        "expected_source": "Calendar",
        "answerable": True,
    },
    {
        "id": "adm_06",
        "category": "admission",
        "question": "What is the reporting and physical registration procedure for newly admitted students?",
        "expected_facts": ["reporting", "registration"],
        "expected_source": "Calendar",
        "answerable": True,
    },
    {
        "id": "adm_07",
        "category": "admission",
        "question": "What are the B.Tech specialisations offered in Computer Science and Engineering?",
        "expected_facts": ["Artificial Intelligence", "Data Science"],
        "expected_source": "Engineering Brochure",
        "answerable": True,
    },
    {
        "id": "adm_08",
        "category": "admission",
        "question": "What specialisations are available in the BBA programme?",
        "expected_facts": ["Banking", "Finance", "Analytics"],
        "expected_source": "Fee Structure",
        "answerable": True,
    },

    # =========================================================================
    # 8. CONTACTS & LOCATION (6 questions)
    # =========================================================================
    {
        "id": "contact_01",
        "category": "contacts",
        "question": "What is the official phone number of the JKLU Admissions Office?",
        "expected_facts": ["8302223344"],
        "expected_source": "Contact",
        "answerable": True,
    },
    {
        "id": "contact_02",
        "category": "contacts",
        "question": "What is the official email address for admission inquiries?",
        "expected_facts": ["admissions@jklu.edu.in"],
        "expected_source": "Contact",
        "answerable": True,
    },
    {
        "id": "contact_03",
        "category": "contacts",
        "question": "Where is the JK Lakshmipat University campus located?",
        "expected_facts": ["Mahapura", "Jaipur"],
        "expected_source": "Contact",
        "answerable": True,
    },
    {
        "id": "contact_04",
        "category": "contacts",
        "question": "What is the telephone number of the Registrar office?",
        "expected_facts": ["7107500"],
        "expected_source": "Contact",
        "answerable": True,
    },
    {
        "id": "contact_05",
        "category": "contacts",
        "question": "What emergency contact numbers are available on campus?",
        "expected_facts": ["security", "emergency"],
        "expected_source": "Emergency Contacts",
        "answerable": True,
    },
    {
        "id": "contact_06",
        "category": "contacts",
        "question": "What is the URL of the official university website?",
        "expected_facts": ["jklu.edu.in"],
        "expected_source": "Contact",
        "answerable": True,
    },

    # =========================================================================
    # 9. FOLLOW-UP QUESTIONS WITH CONTEXT HISTORY (6 questions)
    # =========================================================================
    {
        "id": "follow_01",
        "category": "followup",
        "question": "What is the annual fee for it?",
        "expected_facts": ["2,84,000"],
        "expected_source": "Fee Structure",
        "answerable": True,
        "history": [
            {"role": "user", "content": "Tell me about the Bachelor of Technology (B.Tech) program."},
            {"role": "assistant", "content": "JKLU offers a 4-year B.Tech programme in Computer Science and Engineering."}
        ]
    },
    {
        "id": "follow_02",
        "category": "followup",
        "question": "What are the eligibility criteria?",
        "expected_facts": ["60%", "10+2"],
        "expected_source": "Admission",
        "answerable": True,
        "history": [
            {"role": "user", "content": "I want to apply for BBA."},
            {"role": "assistant", "content": "JKLU offers 3-year and 4-year BBA programmes in Management."}
        ]
    },
    {
        "id": "follow_03",
        "category": "followup",
        "question": "What is his designation and department?",
        "expected_facts": ["Associate Professor", "Computer Science"],
        "expected_source": "faculty",
        "answerable": True,
        "history": [
            {"role": "user", "content": "Who is Dr. Amit Sinhal?"},
            {"role": "assistant", "content": "Dr. Amit Sinhal is a faculty member at JKLU with expertise in computer science and engineering."}
        ]
    },
    {
        "id": "follow_04",
        "category": "followup",
        "question": "How much scholarship can I get with 96 percentile?",
        "expected_facts": ["100%"],
        "expected_source": "Scholarship",
        "answerable": True,
        "history": [
            {"role": "user", "content": "I took JEE Main exam for B.Tech."},
            {"role": "assistant", "content": "JKLU considers JEE Main percentiles for B.Tech admissions and scholarships."}
        ]
    },
    {
        "id": "follow_05",
        "category": "followup",
        "question": "Are food and dining included in it?",
        "expected_facts": ["mess", "meals"],
        "expected_source": "Hostel",
        "answerable": True,
        "history": [
            {"role": "user", "content": "What are the hostel room options at JKLU?"},
            {"role": "assistant", "content": "Hostels provide AC and non-AC rooms with single, double, and triple occupancy."}
        ]
    },
    {
        "id": "follow_06",
        "category": "followup",
        "question": "What was the highest package offered to them?",
        "expected_facts": ["22.5 LPA"],
        "expected_source": "Placement",
        "answerable": True,
        "history": [
            {"role": "user", "content": "Tell me about the engineering batch placements."},
            {"role": "assistant", "content": "JKLU B.Tech students achieved strong placement outcomes in top technology firms."}
        ]
    },

    # =========================================================================
    # 10. TYPOS / HINGLISH / SHORT-FORM QUERIES (10 questions)
    # =========================================================================
    {
        "id": "typo_01",
        "category": "hinglish_typo",
        "question": "btech cse fee",
        "expected_facts": ["2,84,000"],
        "expected_source": "Fee Structure",
        "answerable": True,
    },
    {
        "id": "typo_02",
        "category": "hinglish_typo",
        "question": "bdes eligiblity criteria kya hai?",
        "expected_facts": ["60%"],
        "expected_source": "Admission",
        "answerable": True,
    },
    {
        "id": "typo_03",
        "category": "hinglish_typo",
        "question": "hostel room timing and rules",
        "expected_facts": ["security", "hostel"],
        "expected_source": "Hostel",
        "answerable": True,
    },
    {
        "id": "typo_04",
        "category": "hinglish_typo",
        "question": "placement me kitna package milta hai highest?",
        "expected_facts": ["22.5 LPA"],
        "expected_source": "Placement",
        "answerable": True,
    },
    {
        "id": "typo_05",
        "category": "hinglish_typo",
        "question": "jee main percentile 92 scholarship milegi?",
        "expected_facts": ["75%"],
        "expected_source": "Scholarship",
        "answerable": True,
    },
    {
        "id": "typo_06",
        "category": "hinglish_typo",
        "question": "jklu jaipur me kahan hai campus location",
        "expected_facts": ["Mahapura", "Jaipur"],
        "expected_source": "Contact",
        "answerable": True,
    },
    {
        "id": "typo_07",
        "category": "hinglish_typo",
        "question": "admision application steps",
        "expected_facts": ["application", "register"],
        "expected_source": "Admission",
        "answerable": True,
    },
    {
        "id": "typo_08",
        "category": "hinglish_typo",
        "question": "cse faculty kon kon hai",
        "expected_facts": ["Amit Sinhal", "Sanjay Goel"],
        "expected_source": "faculty",
        "answerable": True,
    },
    {
        "id": "typo_09",
        "category": "hinglish_typo",
        "question": "sabrang fest kab hota hai",
        "expected_facts": ["Sabrang"],
        "expected_source": "Calendar",
        "answerable": True,
    },
    {
        "id": "typo_10",
        "category": "hinglish_typo",
        "question": "bba me kpmg specialization charges kitne hai",
        "expected_facts": ["40,000"],
        "expected_source": "Fee Structure",
        "answerable": True,
    },

    # =========================================================================
    # 11. GENUINELY UNANSWERABLE / OUT-OF-CORPUS (10 questions)
    # MUST correctly escalate / refuse
    # =========================================================================
    {
        "id": "unans_01",
        "category": "unanswerable",
        "question": "What is the NEET cut-off marks for MBBS admission at JKLU?",
        "expected_facts": [],
        "expected_source": "none",
        "answerable": False,
    },
    {
        "id": "unans_02",
        "category": "unanswerable",
        "question": "Who won the 2022 FIFA World Cup final in Qatar?",
        "expected_facts": [],
        "expected_source": "none",
        "answerable": False,
    },
    {
        "id": "unans_03",
        "category": "unanswerable",
        "question": "What will be the annual hostel fee for double AC occupancy in the year 2045?",
        "expected_facts": [],
        "expected_source": "none",
        "answerable": False,
    },
    {
        "id": "unans_04",
        "category": "unanswerable",
        "question": "Does JKLU offer an undergraduate B.Tech in Aerospace Engineering?",
        "expected_facts": [],
        "expected_source": "none",
        "answerable": False,
    },
    {
        "id": "unans_05",
        "category": "unanswerable",
        "question": "What is the hostel dining mess dinner menu for Diwali celebration in 2029?",
        "expected_facts": [],
        "expected_source": "none",
        "answerable": False,
    },
    {
        "id": "unans_06",
        "category": "unanswerable",
        "question": "What are the cutoff ranks for the Master of Pharmacy (M.Pharm) entrance test at JKLU?",
        "expected_facts": [],
        "expected_source": "none",
        "answerable": False,
    },
    {
        "id": "unans_07",
        "category": "unanswerable",
        "question": "What is the syllabus for the 5-year integrated BA LLB law entrance examination at JKLU?",
        "expected_facts": [],
        "expected_source": "none",
        "answerable": False,
    },
    {
        "id": "unans_08",
        "category": "unanswerable",
        "question": "How many students were admitted to the Bachelor of Dental Surgery (BDS) in 2023?",
        "expected_facts": [],
        "expected_source": "none",
        "answerable": False,
    },
    {
        "id": "unans_09",
        "category": "unanswerable",
        "question": "What is the public bus route number and ticket fare from New Delhi railway station to JKLU?",
        "expected_facts": [],
        "expected_source": "none",
        "answerable": False,
    },
    {
        "id": "unans_10",
        "category": "unanswerable",
        "question": "Who is the current Prime Minister of Australia and what is their education?",
        "expected_facts": [],
        "expected_source": "none",
        "answerable": False,
    },
]


def write_gold_dataset():
    lines = [json.dumps(q, ensure_ascii=False) for q in GOLD_QUESTIONS]
    GOLD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Successfully wrote {len(GOLD_QUESTIONS)} gold evaluation questions to {GOLD_PATH}")


if __name__ == "__main__":
    write_gold_dataset()

