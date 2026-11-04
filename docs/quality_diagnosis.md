# JKLU Assistant - Quality Diagnosis & Failure Taxonomy

**Total Evaluated Questions**: 100
**Total Failing Queries**: 26

## 1. Summary Counts by Root-Cause Category

| Category | Code | Failure Count | Description |
| :--- | :---: | :---: | :--- |
| **Chunk never retrieved (sparse/dense miss or term mismatch)** | `(a)` | **14** | a_chunk_never_retrieved |
| **Chunk retrieved but ranked outside top-k** | `(b)` | **0** | b_chunk_ranked_too_low |
| **Chunk retrieved but fact truncated/cut off** | `(c)` | **4** | c_chunk_cut_off |
| **Query router picked wrong category filter** | `(d)` | **0** | d_router_mismatch |
| **LLM prompt had facts in context but dropped or hallucinated them** | `(e)` | **3** | e_llm_dropped_or_hallucinated |
| **Follow-up question resolution failed (missed prior conversational turn)** | `(f)` | **0** | f_followup_resolution_failed |
| **Learning memory returned poisoned/outdated answer** | `(g)` | **0** | g_learning_memory_mismatch |
| **Unanswerable query answered with false claims instead of escalating** | `(h)` | **5** | h_unanswerable_missing_data |

## 2. In-Depth Failure Analysis with Concrete Examples

### (a) Chunk never retrieved (sparse/dense miss or term mismatch) (Count: 14)
- **Query [ID elig_07]**: `"Does JKLU allow diploma holders to apply for lateral entry into B.Tech second year?"`
  - **Expected Fact(s)**: `['lateral entry', 'diploma']`
  - **Retrieved Chunks / Sources**: `['B.Tech Programme']`
  - **Actual Bot Answer**: `"### B.Tech CSE (Computer Science and Engineering):
- The Bachelor of Technology in Computer Science and Engineering prov..."`
- **Query [ID elig_08]**: `"Can students from any 12th stream (Arts/Science/Commerce) apply for B.Des?"`
  - **Expected Fact(s)**: `['any stream', 'recognized board']`
  - **Retrieved Chunks / Sources**: `['B.Des (Product Design)']`
  - **Actual Bot Answer**: `"Based on the provided context, students from **any** 12th stream (Arts, Science, or Commerce) can apply for the B.Des pr..."`
- **Query [ID sch_01]**: `"What scholarship is awarded to B.Tech applicants with a JEE Main percentile of 95 or above?"`
  - **Expected Fact(s)**: `['100%', 'academic fee']`
  - **Retrieved Chunks / Sources**: `['B.Tech Programme']`
  - **Actual Bot Answer**: `"### B.Tech CSE (Computer Science and Engineering):
- The Bachelor of Technology in Computer Science and Engineering prov..."`

### (b) Chunk retrieved but ranked outside top-k (Count: 0)
_No failures recorded in this category._

### (c) Chunk retrieved but fact truncated/cut off (Count: 4)
- **Query [ID fee_02]**: `"How much is the tuition fee for the Bachelor of Design (B.Des) programme?"`
  - **Expected Fact(s)**: `['3,05,000']`
  - **Retrieved Chunks / Sources**: `['Fee Structure', 'Jklu Fee Structure 2026 27']`
  - **Actual Bot Answer**: `"Based on the provided context, the tuition (Academic) fee for the **Bachelor of Design** programme for the Academic Year..."`
- **Query [ID fee_10]**: `"Where can students obtain the official admission withdrawal application form?"`
  - **Expected Fact(s)**: `['Withdrawal Application Form', 'admissions']`
  - **Retrieved Chunks / Sources**: `['Application Withdrawal Form 2026', 'Application Withdrawal Form 2026']`
  - **Actual Bot Answer**: `"- Note: The refund will be completed within 30 days of submitting the application along with the necessary documents. [1..."`
- **Query [ID sch_07]**: `"Is there any financial assistance or government scholarship program supported at JKLU?"`
  - **Expected Fact(s)**: `['Vidya Lakshmi', 'education loan']`
  - **Retrieved Chunks / Sources**: `['Placement Registration Eligibility And Career Services', 'International Admissions']`
  - **Actual Bot Answer**: `"- **Graduation Benchmark**: Minimum graduation/programme CGPA required at the time of final onboarding. [2]
- Our admiss..."`

### (d) Query router picked wrong category filter (Count: 0)
_No failures recorded in this category._

### (e) LLM prompt had facts in context but dropped or hallucinated them (Count: 3)
- **Query [ID fee_04]**: `"What is the annual academic fee for the M.Tech programme?"`
  - **Expected Fact(s)**: `['1,80,000']`
  - **Retrieved Chunks / Sources**: `['Placement Registration Eligibility And Career Services', 'Placement Registration Eligibility And Career Services']`
  - **Actual Bot Answer**: `"Based on the provided context, the tuition fee for B Tech (Bachelor of Technology) at JK Lakshmipat University is:


Aca..."`
- **Query [ID hostel_04]**: `"Are laundry and washing facilities available on campus?"`
  - **Expected Fact(s)**: `['laundry']`
  - **Retrieved Chunks / Sources**: `['Hostel Life Policy']`
  - **Actual Bot Answer**: `"### JKLU Campus & Infrastructure Overview:
- **Campus Area**: JK Lakshmipat University is spread across a spacious **30-..."`
- **Query [ID contact_05]**: `"What emergency contact numbers are available on campus?"`
  - **Expected Fact(s)**: `['security', 'emergency']`
  - **Retrieved Chunks / Sources**: `['Campus Emergency Contacts And Safety Facilities']`
  - **Actual Bot Answer**: `"### JKLU Campus & Infrastructure Overview:
- **Campus Area**: JK Lakshmipat University is spread across a spacious **30-..."`

### (f) Follow-up question resolution failed (missed prior conversational turn) (Count: 0)
_No failures recorded in this category._

### (g) Learning memory returned poisoned/outdated answer (Count: 0)
_No failures recorded in this category._

### (h) Unanswerable query answered with false claims instead of escalating (Count: 5)
- **Query [ID unans_01]**: `"What is the NEET cut-off marks for MBBS admission at JKLU?"`
  - **Expected Fact(s)**: `['Proper refusal / escalation']`
  - **Retrieved Chunks / Sources**: `['JKLU Regulations (examination, grading, attendance)', 'JKLU Regulations (examination, grading, attendance)']`
  - **Actual Bot Answer**: `"I’m sorry, but the provided context does not contain any information about the NEET cut‑off marks for MBBS admission at ..."`
- **Query [ID unans_04]**: `"Does JKLU offer an undergraduate B.Tech in Aerospace Engineering?"`
  - **Expected Fact(s)**: `['Proper refusal / escalation']`
  - **Retrieved Chunks / Sources**: `['B.Tech Programme']`
  - **Actual Bot Answer**: `"Based on the provided context, JK Lakshmipat University (JKLU) **does not** list an undergraduate B.Tech program in Aero..."`
- **Query [ID unans_06]**: `"What are the cutoff ranks for the Master of Pharmacy (M.Pharm) entrance test at JKLU?"`
  - **Expected Fact(s)**: `['Proper refusal / escalation']`
  - **Retrieved Chunks / Sources**: `['Jklu Admission Process 2026 27', 'Jklu Admission Process 2026 27']`
  - **Actual Bot Answer**: `"I couldn’t find any information about cutoff ranks for the Master of Pharmacy (M Pharm) entrance test at JKLU in the pro..."`
