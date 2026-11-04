# JKLU Assistant - Latency Profiling Report

**Date**: 2026-11-04 15:20:42 UTC  
**Queries Profiled**: 19  
**Configured Groq Model**: `qwen/qwen3.8-27b`  
**Cold Boot Time**: 50.298s  
**Cold First Query Time**: 22721.49 ms  
**RSS Memory**: Start = 66.2 MB | Post-Init = 348.8 MB | Final = 360.6 MB  

## 1. Top 3 Bottlenecks Ranked by Time Spent

### #1: `page_fetch_ms`
- **Mean**: 6261.6 ms | **p50**: 6261.6 ms | **p95**: 7107.0 ms | **Max**: 7200.9 ms
- **Root Cause**: Tier 2 live fetch triggers on keywords like `'2026-27'` or `'schedule'` even when answers already exist in the index, firing blocking HTTP requests over the network.
### #2: `memory_lookup_ms`
- **Mean**: 5471.5 ms | **p50**: 1593.2 ms | **p95**: 14343.7 ms | **Max**: 18541.4 ms
- **Root Cause**: `SelfAgenticMemory.recall()` performs linear dense matrix multiplication across all 400+ phrasing patterns and runs dynamic synonym-overlap comparisons on every query synchronously.
### #3: `llm_time_to_first_token_ms`
- **Mean**: 835.8 ms | **p50**: 1156.0 ms | **p95**: 1265.9 ms | **Max**: 1265.9 ms
- **Root Cause**: LLM token generation latency and HTTP 429 rate limits on `qwen/qwen3.8-27b`, causing token stalls and extractive retries.

## 2. Complete Latency Breakdown Table

| Stage | p50 (ms) | p95 (ms) | Mean (ms) | Max (ms) |
| :--- | :---: | :---: | :---: | :---: |
| **Overall Request Latency** | **11178.4** | **36264.6** | **15625.4** | **54271.6** |
| `page_fetch_ms` | 6261.6 | 7107.0 | 6261.6 | 7200.9 |
| `memory_lookup_ms` | 1593.2 | 14343.7 | 5471.5 | 18541.4 |
| `llm_time_to_first_token_ms` | 1156.0 | 1265.9 | 835.8 | 1265.9 |
| `llm_total_ms` | 1156.0 | 1265.9 | 835.8 | 1265.9 |
| `live_fetch_total_ms` | 0.0 | 5520.5 | 659.8 | 7202.1 |
| `retrieval_total_ms` | 134.9 | 451.1 | 175.1 | 519.6 |
| `query_embedding_ms` | 96.9 | 329.7 | 125.6 | 410.6 |
| `bm25_search_ms` | 6.1 | 110.6 | 25.4 | 168.9 |
| `faiss_search_ms` | 0.8 | 57.9 | 11.6 | 136.1 |
| `query_classification_ms` | 7.4 | 14.8 | 6.9 | 16.8 |
| `robots_sitemap_ms` | 6.2 | 10.8 | 6.2 | 11.3 |
| `rrf_fusion_ms` | 0.2 | 0.6 | 0.4 | 3.2 |
| `prompt_building_ms` | 0.4 | 0.4 | 0.3 | 0.4 |
| `post_processing_ms` | 0.1 | 1.8 | 0.3 | 2.9 |
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
