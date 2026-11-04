# JKLU Assistant - Evaluation Report

**Date**: 2026-11-04 15:13:05 UTC  
**Total Questions**: 100 (90 Answerable, 10 Unanswerable)  
**Embedding Model**: FastEmbed (ONNX) `all-MiniLM-L6-v2`  
**LLM Provider**: `groq` (`None`)  

## 1. Overall RAG Quality & Accuracy Metrics

| Metric | Target | Result | Status |
| :--- | :---: | :---: | :---: |
| **Retrieval Hit@1** | $\ge 70\%$ | **66.7%** | ⚠️ |
| **Retrieval Hit@3** | $\ge 85\%$ | **72.2%** | ⚠️ |
| **Retrieval Hit@5** | $\ge 90\%$ | **72.2%** | ⚠️ |
| **Answer Fact-Recall** | $\ge 80\%$ | **67.1%** | ⚠️ |
| **Wrong-Answer Rate** | $\le 15\%$ | **26.0%** | ⚠️ |
| **Unanswerable Refusal Rate** | $\ge 80\%$ | **50.0%** | ⚠️ |

## 2. Latency Breakdown per Stage

| Stage | p50 (ms) | p95 (ms) | Mean (ms) |
| :--- | :---: | :---: | :---: |
| **End-to-End Latency** | **3790.2** | **7691.5** | **3786.2** |
| `total_ms` | 1890.5 | 4239.0 | 2021.1 |
| `total_live_fetch_ms` | 1818.0 | 2598.9 | 1927.0 |
| `page_fetch_ms` | 1817.3 | 2598.0 | 1926.2 |
| `memory_lookup_ms` | 1034.5 | 1864.2 | 1039.6 |
| `llm_time_to_first_token_ms` | 0.0 | 1359.9 | 305.2 |
| `llm_total_ms` | 0.0 | 1359.9 | 305.2 |
| `live_fetch_total_ms` | 0.0 | 1821.4 | 212.0 |
| `retrieval_total_ms` | 17.2 | 34.2 | 18.0 |
| `query_classification_ms` | 8.4 | 27.7 | 10.8 |
| `query_embedding_ms` | 5.7 | 9.9 | 6.0 |
| `bm25_search_ms` | 2.5 | 6.8 | 3.0 |
| `faiss_search_ms` | 1.5 | 3.2 | 1.3 |
| `robots_sitemap_ms` | 0.7 | 1.4 | 0.8 |
| `rrf_fusion_ms` | 0.1 | 0.3 | 0.2 |
| `prompt_building_ms` | 0.2 | 0.6 | 0.2 |
| `post_processing_ms` | 0.0 | 0.1 | 0.0 |
| `parse_chunk_ms` | 0.0 | 0.0 | 0.0 |
| `embed_rerank_ms` | 0.0 | 0.0 | 0.0 |

## 3. Breakdown by Category

| Category | Questions | Correct | Fact Recall | Accuracy |
| :--- | :---: | :---: | :---: | :---: |
| **admission** | 8 | 7 | 66.7% | 87.5% |
| **campus_life** | 5 | 4 | 72.7% | 80.0% |
| **contacts** | 6 | 3 | 50.0% | 50.0% |
| **eligibility** | 10 | 8 | 60.0% | 80.0% |
| **faculty** | 10 | 9 | 72.2% | 90.0% |
| **fees** | 12 | 10 | 75.0% | 83.3% |
| **followup** | 6 | 4 | 55.6% | 66.7% |
| **hinglish_typo** | 10 | 8 | 71.4% | 80.0% |
| **hostel** | 5 | 4 | 90.0% | 80.0% |
| **placements** | 10 | 9 | 87.5% | 90.0% |
| **scholarships** | 8 | 3 | 28.6% | 37.5% |
| **unanswerable** | 10 | 5 | 100.0% | 50.0% |

## 4. Notable Failures & Regressions

- **[fees]** `How much is the tuition fee for the Bachelor of Design (B.Des) programme?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
- **[fees]** `Where can students obtain the official admission withdrawal application form?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
- **[eligibility]** `Does JKLU allow diploma holders to apply for lateral entry into B.Tech second year?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
- **[eligibility]** `Can students from any 12th stream (Arts/Science/Commerce) apply for B.Des?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
- **[scholarships]** `What scholarship is awarded to B.Tech applicants with a JEE Main percentile of 95 or above?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
- **[scholarships]** `What scholarship percentage is offered for JEE Main percentile between 90 and 95?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
- **[scholarships]** `What scholarship waiver is available for students scoring 85 to 90 percentile in JEE Main?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
- **[scholarships]** `Is there any financial assistance or government scholarship program supported at JKLU?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
- **[scholarships]** `What scholarship can BBA students get for high Class 12 board percentages?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
- **[placements]** `What is the placement percentage for registered and eligible B.Tech students?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
- **[faculty]** `Who are the CSE faculty at JKLU?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
- **[hostel]** `Are laundry and washing facilities available on campus?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
- **[campus_life]** `What medical and health facilities are available on campus for students?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
- **[admission]** `What are the B.Tech specialisations offered in Computer Science and Engineering?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
- **[contacts]** `What is the official phone number of the JKLU Admissions Office?` -> *Status*: `answer` | *Verdict*: `fail (0 facts recalled)`
