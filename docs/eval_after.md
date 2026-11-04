# JKLU Assistant - Evaluation Report

**Date**: 2026-11-04 16:29:55 UTC  
**Total Questions**: 100 (90 Answerable, 10 Unanswerable)  
**Embedding Model**: FastEmbed (ONNX) `all-MiniLM-L6-v2`  
**LLM Provider**: `groq` (`None`)  

## 1. Overall RAG Quality & Accuracy Metrics

| Metric | Target | Result | Status |
| :--- | :---: | :---: | :---: |
| **Retrieval Hit@1** | $\ge 70\%$ | **71.1%** | ✅ |
| **Retrieval Hit@3** | $\ge 85\%$ | **72.2%** | ⚠️ |
| **Retrieval Hit@5** | $\ge 90\%$ | **73.3%** | ⚠️ |
| **Answer Fact-Recall** | $\ge 80\%$ | **69.0%** | ⚠️ |
| **Wrong-Answer Rate** | $\le 15\%$ | **20.0%** | ⚠️ |
| **Unanswerable Refusal Rate** | $\ge 80\%$ | **90.0%** | ✅ |

## 2. Latency Breakdown per Stage

| Stage | p50 (ms) | p95 (ms) | Mean (ms) |
| :--- | :---: | :---: | :---: |
| **End-to-End Latency** | **759.2** | **1898.1** | **892.4** |
| `total_live_fetch_ms` | 1620.7 | 4834.3 | 2442.4 |
| `page_fetch_ms` | 1619.8 | 4832.5 | 2441.3 |
| `total_ms` | 759.0 | 1897.8 | 892.2 |
| `llm_time_to_first_token_ms` | 0.0 | 1165.1 | 128.4 |
| `llm_total_ms` | 0.0 | 1165.1 | 128.4 |
| `live_fetch_total_ms` | 0.0 | 0.0 | 97.7 |
| `retrieval_total_ms` | 17.9 | 36.3 | 17.3 |
| `query_classification_ms` | 8.6 | 24.2 | 9.9 |
| `query_embedding_ms` | 5.5 | 11.9 | 5.4 |
| `bm25_search_ms` | 2.5 | 8.5 | 3.0 |
| `faiss_search_ms` | 1.0 | 2.6 | 1.1 |
| `robots_sitemap_ms` | 0.9 | 1.8 | 1.1 |
| `rrf_fusion_ms` | 0.1 | 0.3 | 0.2 |
| `prompt_building_ms` | 0.2 | 0.4 | 0.2 |
| `memory_lookup_ms` | 0.0 | 0.0 | 0.0 |
| `post_processing_ms` | 0.0 | 0.1 | 0.0 |
| `parse_chunk_ms` | 0.0 | 0.0 | 0.0 |
| `embed_rerank_ms` | 0.0 | 0.0 | 0.0 |

## 3. Breakdown by Category

| Category | Questions | Correct | Fact Recall | Accuracy |
| :--- | :---: | :---: | :---: | :---: |
| **admission** | 8 | 8 | 83.3% | 100.0% |
| **campus_life** | 5 | 4 | 81.8% | 80.0% |
| **contacts** | 6 | 3 | 50.0% | 50.0% |
| **eligibility** | 10 | 7 | 50.0% | 70.0% |
| **faculty** | 10 | 9 | 72.2% | 90.0% |
| **fees** | 12 | 11 | 80.0% | 91.7% |
| **followup** | 6 | 4 | 55.6% | 66.7% |
| **hinglish_typo** | 10 | 9 | 78.6% | 90.0% |
| **hostel** | 5 | 4 | 90.0% | 80.0% |
| **placements** | 10 | 8 | 68.8% | 80.0% |
| **scholarships** | 8 | 4 | 42.9% | 50.0% |
| **unanswerable** | 10 | 9 | 100.0% | 90.0% |

## 4. Notable Failures & Regressions

- **[fees]** `What is the fee refund policy if a student withdraws before the academic session starts?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
- **[eligibility]** `What entrance exam is conducted for Bachelor of Design admissions?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
- **[eligibility]** `Does JKLU allow diploma holders to apply for lateral entry into B.Tech second year?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
- **[eligibility]** `Can students from any 12th stream (Arts/Science/Commerce) apply for B.Des?` -> *Status*: `escalate` | *Verdict*: `fail (false refusal)`
- **[scholarships]** `What is the minimum CGPA requirement to renew the merit scholarship in subsequent years?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
- **[scholarships]** `Can scholarships be combined or do students receive the single highest scholarship?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
- **[scholarships]** `Is there any financial assistance or government scholarship program supported at JKLU?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
- **[scholarships]** `What scholarship can BBA students get for high Class 12 board percentages?` -> *Status*: `escalate` | *Verdict*: `fail (false refusal)`
- **[placements]** `What was the highest package (CTC) offered to B.Tech students in the 2024 batch?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
- **[placements]** `What is the minimum attendance or eligibility criterion for students to participate in campus placements?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
- **[faculty]** `Who are the CSE faculty at JKLU?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
- **[hostel]** `Are laundry and washing facilities available on campus?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
- **[campus_life]** `What medical and health facilities are available on campus for students?` -> *Status*: `escalate` | *Verdict*: `fail (false refusal)`
- **[contacts]** `What is the official phone number of the JKLU Admissions Office?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
- **[contacts]** `What is the official email address for admission inquiries?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
