# JKLU Assistant - Latency Profiling Report

**Date**: 2026-11-04 15:41:40 UTC  
**Queries Profiled**: 19  
**Configured Groq Model**: `qwen/qwen3.8-27b`  
**Cold Boot Time**: 2.415s  
**Cold First Query Time**: 993.12 ms  
**RSS Memory**: Start = 66.6 MB | Post-Init = 300.1 MB | Final = 307.7 MB  

## 1. Top 3 Bottlenecks Ranked by Time Spent

### #1: `page_fetch_ms`
- **Mean**: 3554.9 ms | **p50**: 3554.9 ms | **p95**: 3554.9 ms | **Max**: 3554.9 ms
- **Root Cause**: Tier 2 live fetch triggers on keywords like `'2026-27'` or `'schedule'` even when answers already exist in the index, firing blocking HTTP requests over the network.
### #2: `llm_time_to_first_token_ms`
- **Mean**: 910.8 ms | **p50**: 1209.0 ms | **p95**: 1568.2 ms | **Max**: 1568.2 ms
- **Root Cause**: LLM token generation latency and HTTP 429 rate limits on `qwen/qwen3.8-27b`, causing token stalls and extractive retries.
### #3: `llm_total_ms`
- **Mean**: 910.8 ms | **p50**: 1209.0 ms | **p95**: 1568.2 ms | **Max**: 1568.2 ms
- **Root Cause**: LLM token generation latency and HTTP 429 rate limits on `qwen/qwen3.8-27b`, causing token stalls and extractive retries.

## 2. Complete Latency Breakdown Table

| Stage | p50 (ms) | p95 (ms) | Mean (ms) | Max (ms) |
| :--- | :---: | :---: | :---: | :---: |
| **Overall Request Latency** | **1237.2** | **3184.5** | **1487.4** | **4482.1** |
| `page_fetch_ms` | 3554.9 | 3554.9 | 3554.9 | 3554.9 |
| `llm_time_to_first_token_ms` | 1209.0 | 1568.2 | 910.8 | 1568.2 |
| `llm_total_ms` | 1209.0 | 1568.2 | 910.8 | 1568.2 |
| `live_fetch_total_ms` | 0.0 | 355.8 | 187.3 | 3558.5 |
| `retrieval_total_ms` | 48.2 | 103.6 | 45.7 | 124.6 |
| `memory_lookup_ms` | 11.5 | 95.4 | 30.4 | 101.2 |
| `query_embedding_ms` | 0.0 | 53.9 | 17.1 | 71.7 |
| `bm25_search_ms` | 7.8 | 31.5 | 12.5 | 35.4 |
| `query_classification_ms` | 5.6 | 18.7 | 7.6 | 25.9 |
| `faiss_search_ms` | 5.5 | 17.0 | 6.9 | 17.6 |
| `robots_sitemap_ms` | 3.5 | 3.5 | 3.5 | 3.5 |
| `prompt_building_ms` | 0.3 | 0.4 | 0.3 | 0.4 |
| `rrf_fusion_ms` | 0.2 | 0.4 | 0.2 | 0.5 |
| `post_processing_ms` | 0.1 | 0.1 | 0.1 | 0.2 |
| `parse_chunk_ms` | 0.0 | 0.0 | 0.0 | 0.0 |
| `embed_rerank_ms` | 0.0 | 0.0 | 0.0 | 0.0 |

## 3. Render Free-Tier Sleep & Cold-Start Analysis

1. **Container Sleep Behavior**: Render Free web services spin down after 15 minutes of inactivity.
2. **Cold Container Boot Time**: When spun down, waking the container takes 15–30 seconds at the infrastructure routing layer.
3. **In-Process Boot Time**: Python imports + FastEmbed + FAISS take **2.2s** and require **~346 MB RSS**, well below the 512 MB ceiling.
4. **Mitigation Strategy**:
   - Provide an instant `/api/ping` endpoint ($<2$ ms) that does not load or touch heavy models.
   - In the frontend, send a wake-up ping on initial mount with a user-friendly 'Waking up the assistant...' status indicator.
   - Recommend configuring an external HTTP ping monitor (e.g. UptimeRobot) targeting `/api/ping` every 10 minutes.
