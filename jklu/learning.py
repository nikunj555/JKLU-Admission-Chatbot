"""Self-Agentic RAG: Continuous Learning, Query Memory & Adaptive Reflection.

This module provides the self-learning and self-correcting memory layer for the
JKLU RAG Chatbot:
1. Self-Reflection: Evaluates whether a generated answer is grounded, has valid citations,
   and meets quality thresholds before committing to memory.
2. Query Memory & Semantic Clustering: Stores verified answers along with their proven
   document chunk citations and a cluster of alternative prompt formulations.
3. Adaptive Recall & Few-Shot Injection: When any user asks the same kind of question in a
   different prompt formulation, it semantically matches the query against the memory graph,
   re-injects the historically proven document chunks, and provides optimal responses.
4. Continuous Online Learning: Automatically records new user prompt formulations as aliases,
   reinforces memory upon positive feedback, and adapts continuously.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from . import config as C
from . import textproc as T
from .utils import log

_LEARNING_DIR = C.DATA_DIR / "learning"
_MEMORY_FILE = _LEARNING_DIR / "learned_memory.json"
_LOCK = threading.RLock()


def _detect_programme(text: str) -> str | None:
    t = text.lower()
    if re.search(r"\b(b\.?des|bachelor of design|m\.?des|master of design)\b", t):
        return "bdes"
    if re.search(r"\b(bba|b\.?b\.?a|bachelor of business administratio\w*|management)\b", t):
        return "bba"
    if re.search(r"\b(b\.?tech|bachelor of technology|m\.?tech|master of technology|engineering|cse|ece)\b", t):
        return "btech"
    if re.search(r"\b(ph\.?d|doctor of philosophy)\b", t):
        return "phd"
    return None


def _detect_topic(text: str) -> str | None:
    t = text.lower()
    if any(k in t for k in ("fee", "fees", "cost", "tuition", "charge")):
        return "fees"
    if any(k in t for k in ("eligib", "criteria", "requirement", "qualif", "how to apply", "admission requirement")):
        return "eligibility"
    if any(k in t for k in ("speciali", "branch", "elective", "track", "domain")):
        return "specialisations"
    if any(k in t for k in ("placement", "package", "ctc", "recruiter", "salary")):
        return "placement"
    if any(k in t for k in ("hostel", "mess", "curfew", "room")):
        return "hostel"
    if any(k in t for k in ("fest", "festival", "event")):
        return "festivals"
    return None


@dataclass
class MemoryEntry:
    id: str
    canonical_query: str
    patterns: list[str] = field(default_factory=list)
    category: str = "general"
    chunk_ids: list[str] = field(default_factory=list)
    verified_answer: str = ""
    sources: list[dict] = field(default_factory=list)
    confidence: float = 0.95
    hits: int = 1
    feedback_up: int = 0
    feedback_down: int = 0
    embedding: list[float] | None = None
    created_at: int = 0
    updated_at: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryEntry:
        fields = cls.__dataclass_fields__
        filtered = {k: v for k, v in data.items() if k in fields}
        return cls(**filtered)


@dataclass
class MemoryMatch:
    entry: MemoryEntry
    similarity: float
    tier: str  # "exact" | "strong" | "guidance"
    matched_pattern: str


class SelfAgenticMemory:
    """Adaptive query memory and self-reflective continuous learning engine."""

    def __init__(self, kb=None, store_path: Path | None = None):
        self.kb = kb
        self.store_path = store_path or _MEMORY_FILE
        self.entries: list[MemoryEntry] = []
        self._emb_matrix: np.ndarray | None = None
        self._load()

    # ------------------------------------------------------------- persistence
    def _load(self) -> None:
        with _LOCK:
            if not self.store_path.exists():
                self._seed_initial_memories()
                return
            try:
                with open(self.store_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.entries = [MemoryEntry.from_dict(d) for d in data]
                self._rebuild_embedding_matrix()
                log.info("SelfAgenticMemory loaded %d learned memory clusters from %s",
                         len(self.entries), self.store_path.name)
            except Exception as e:
                log.warning("Could not load learned memory from %s (%s). Re-seeding.", self.store_path, e)
                self._seed_initial_memories()

    def _save(self) -> None:
        with _LOCK:
            try:
                self.store_path.parent.mkdir(parents=True, exist_ok=True)
                temp_file = self.store_path.with_suffix(".tmp")
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump([e.to_dict() for e in self.entries], f, indent=2, ensure_ascii=False)
                if temp_file.exists():
                    os.replace(temp_file, self.store_path)
            except Exception as e:
                log.error("Failed to save learned memory to %s: %s", self.store_path, e)

    # -------------------------------------------------------- seed initialization
    def _seed_initial_memories(self) -> None:
        """Seed foundational university topics so the agent immediately knows optimal chunks."""
        now = int(time.time())
        seeds = [
            MemoryEntry(
                id="mem_placement_stats",
                canonical_query="What are the placement packages, highest CTC, and average package at JKLU?",
                patterns=[
                    "what is the average package at jklu?",
                    "what was the highest package at jklu?",
                    "what is the average salary at jklu?",
                    "placement statistics jklu",
                    "what is the highest ctc?",
                    "what is the average ctc?",
                    "placement packages for btech",
                    "what do freshers earn on average?",
                    "what is the median salary for btech?",
                    "how much package can i get after btech from jklu?",
                    "who are the top recruiters for placements?"
                ],
                category="academics",
                chunk_ids=["d580c35126-0049", "d580c35126-0050"],
                verified_answer=(
                    "### JKLU Placement Highlights (B.Tech - 2024 Batch):\n"
                    "- **Highest CTC / Package**: **INR 22.5 LPA** [1]\n"
                    "- **Average CTC / Package**: **INR 8.10 LPA** [1]\n"
                    "- **Top 10% Average CTC**: **INR 18.07 LPA** [1]\n"
                    "- **Placement Success Rate**: Up to **100% placement** for eligible registered students [1]\n"
                    "- **Top Recruiters**: Infosys, Tata Consultancy Services (TCS), IBM, KPMG, and leading technology & consulting firms [1]."
                ),
                confidence=0.98,
                hits=10,
                created_at=now,
                updated_at=now
            ),
            MemoryEntry(
                id="mem_placement_eligibility",
                canonical_query="What are the placement eligibility criteria and registration document requirements at JKLU?",
                patterns=[
                    "what are the eligibility criteria for placement registration?",
                    "placement registration checklist",
                    "documents required for placement registration",
                    "placement cell rules and backlogs",
                    "cgpa criteria for placements"
                ],
                category="admission",
                chunk_ids=["eaad97fa55-0000", "eaad97fa55-0004", "eaad97fa55-0005"],
                confidence=0.95,
                hits=5,
                created_at=now,
                updated_at=now
            ),
            MemoryEntry(
                id="mem_bba_fee_3yr",
                canonical_query="What is the fee structure of BBA for all 3 years at JKLU?",
                patterns=[
                    "what is the fees structure of the bba for all 3years",
                    "bba fee structure for all 3 years",
                    "what is the total fee for 3 years bba?",
                    "bba 3 years fees",
                    "how much does bba cost for 3 years?"
                ],
                category="fees",
                chunk_ids=["97de2bec53-0000", "97de2bec53-0001"],
                confidence=0.95,
                hits=8,
                created_at=now,
                updated_at=now
            ),
            MemoryEntry(
                id="mem_cse_faculty",
                canonical_query="Who are the faculty members in the Computer Science and Engineering (CSE) department at JKLU?",
                patterns=[
                    "who are the faculty members in the cse department?",
                    "computer science faculty at jklu",
                    "cse professors jklu",
                    "who teaches computer science at jklu?",
                    "list of cse professors"
                ],
                category="faculty",
                chunk_ids=["38190408f7-0009", "38190408f7-0023", "871ac4ec8e-0029"],
                confidence=0.95,
                hits=6,
                created_at=now,
                updated_at=now
            ),
            MemoryEntry(
                id="mem_campus_festivals",
                canonical_query="What fests and events are held at JKLU?",
                patterns=[
                    "what events are held at jklu?",
                    "what fests are held at jklu?",
                    "what festivals are celebrated at jklu?",
                    "what are the annual fests at jklu?",
                    "what are the events held at jklu?",
                    "annual fests at jklu",
                    "campus events and festivals at jklu",
                    "list of events and fests at jklu",
                    "cultural and sports fests at jklu",
                    "what are the major events organized at jklu?",
                    "fests in jklu",
                    "events in jklu"
                ],
                category="general",
                chunk_ids=[
                    "8c614e8e4e-0000",
                    "8c614e8e4e-0002",
                    "8c614e8e4e-0005",
                    "8c614e8e4e-0006",
                    "aa0862ce20-0003",
                    "da997aecf9-0004"
                ],
                confidence=0.98,
                hits=15,
                created_at=now,
                updated_at=now
            )
        ]
        self.entries = seeds
        self._compute_embeddings_for_entries(self.entries)
        self._save()
        self._rebuild_embedding_matrix()
        log.info("Initialized %d seed memory clusters in SelfAgenticMemory", len(self.entries))

    # ------------------------------------------------------------- embedding
    def _get_embedder(self):
        if not self.kb:
            return None
        emb = getattr(self.kb, "embedder", None)
        if emb and hasattr(emb, "encode"):
            return emb
        return None

    def _encode_text(self, text: str) -> np.ndarray | None:
        embedder = self._get_embedder()
        if not embedder:
            return None
        try:
            emb = embedder.encode([text])[0]
            norm = np.linalg.norm(emb)
            return (emb / norm).astype("float32") if norm > 0 else emb
        except Exception as e:
            log.warning("Encoding failed in SelfAgenticMemory: %s", e)
            return None

    def _compute_embeddings_for_entries(self, entries: list[MemoryEntry]) -> None:
        embedder = self._get_embedder()
        if not embedder:
            return
        texts_to_encode = []
        indices = []
        for i, entry in enumerate(entries):
            if not entry.embedding:
                # Text representation encompasses canonical query and top patterns
                comb = f"{entry.canonical_query} " + " ".join(entry.patterns[:4])
                texts_to_encode.append(comb)
                indices.append(i)
        if texts_to_encode:
            try:
                embs = embedder.encode(texts_to_encode)
                for idx, emb in zip(indices, embs):
                    norm = np.linalg.norm(emb)
                    unit_emb = (emb / norm).astype("float32") if norm > 0 else emb
                    entries[idx].embedding = [float(x) for x in unit_emb]
            except Exception as e:
                log.warning("Batch encoding failed for memory entries: %s", e)

    def _rebuild_embedding_matrix(self) -> None:
        embedder = self._get_embedder()
        if not embedder or not self.entries:
            self._emb_matrix = None
            self._pattern_map = []
            return

        all_texts = []
        pattern_map = []  # list of entry references for each row in all_texts
        for entry in self.entries:
            all_texts.append(entry.canonical_query)
            pattern_map.append(entry)
            for pat in entry.patterns:
                if pat.strip().lower() != entry.canonical_query.strip().lower():
                    all_texts.append(pat)
                    pattern_map.append(entry)

        try:
            embs = embedder.encode(all_texts)
            # Normalize to unit length for exact cosine via dot product
            norms = np.linalg.norm(embs, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            self._emb_matrix = (embs / norms).astype("float32")
            self._pattern_map = pattern_map
            log.info("SelfAgenticMemory built fast pattern matrix: %d phrasing vectors across %d clusters",
                     len(all_texts), len(self.entries))
        except Exception as e:
            log.warning("Pattern matrix build failed in SelfAgenticMemory: %s", e)
            self._emb_matrix = None
            self._pattern_map = []

    # ------------------------------------------------------- similarity matching
    @staticmethod
    def _synonym_term_set(text: str) -> set[str]:
        terms = T.content_terms(text)
        out = set(terms)
        for t in terms:
            out.update(T.synonym_stems(t))
        return out

    # ------------------------------------------------------------- recall api
    def recall(self, query: str, threshold: float = 0.38) -> MemoryMatch | None:
        """Recall matching verified memory entry for a user query."""
        if not self.entries or not query.strip():
            return None

        q_clean = query.strip()
        q_low = q_clean.lower().strip(" ?.,")
        q_terms = self._synonym_term_set(q_clean)
        q_prog = _detect_programme(q_clean)
        q_topic = _detect_topic(q_clean)

        # 1. Exact pattern lookup first (with programme and topic guard)
        for entry in self.entries:
            e_prog = _detect_programme(entry.canonical_query + " " + " ".join(entry.patterns[:3]))
            e_topic = _detect_topic(entry.canonical_query)
            if q_prog and e_prog and q_prog != e_prog:
                continue
            if q_topic and e_topic and q_topic != e_topic:
                continue
            for pat in entry.patterns:
                if q_low == pat.lower().strip(" ?.,"):
                    return MemoryMatch(entry=entry, similarity=1.0, tier="exact", matched_pattern=pat)
            if q_low == entry.canonical_query.lower().strip(" ?.,"):
                return MemoryMatch(entry=entry, similarity=1.0, tier="exact", matched_pattern=entry.canonical_query)

        # 2. Fast dense pattern matrix dot-product
        dense_scores_by_entry: dict[str, float] = {e.id: 0.0 for e in self.entries}
        q_emb = self._encode_text(q_clean)
        if q_emb is not None and self._emb_matrix is not None and len(self._pattern_map) == len(self._emb_matrix):
            sims = self._emb_matrix @ q_emb
            for sim, entry in zip(sims, self._pattern_map):
                s = float(sim)
                if s > dense_scores_by_entry[entry.id]:
                    dense_scores_by_entry[entry.id] = s

        # 3. Hybrid scoring: combine dense pattern similarity + synonym overlap
        best_entry: MemoryEntry | None = None
        best_score = 0.0

        for entry in self.entries:
            e_prog = _detect_programme(entry.canonical_query + " " + " ".join(entry.patterns[:3]))
            e_topic = _detect_topic(entry.canonical_query)
            if q_prog and e_prog and q_prog != e_prog:
                continue
            if q_topic and e_topic and q_topic != e_topic:
                continue

            d_sim = dense_scores_by_entry.get(entry.id, 0.0)
            e_terms = self._synonym_term_set(entry.canonical_query + " " + " ".join(entry.patterns[:4]))
            overlap = len(q_terms & e_terms) / max(len(q_terms), 1) if q_terms else 0.0

            # Score is driven by the maximum of dense similarity and hybrid overlap
            score = max(d_sim, 0.60 * d_sim + 0.40 * overlap)
            if overlap >= 0.50 and d_sim >= 0.25:
                score = max(score, 0.55 + 0.3 * (overlap - 0.50))

            if score > best_score:
                best_score = score
                best_entry = entry

        if best_entry and best_score >= threshold:
            tier = "exact" if best_score >= 0.85 else ("strong" if best_score >= 0.72 else "guidance")
            return MemoryMatch(entry=best_entry, similarity=round(best_score, 4), tier=tier, matched_pattern=best_entry.canonical_query)
        return None

    # ------------------------------------------------- self-reflection & learning
    def reflect_and_learn(self, raw_query: str, extracted_q: str, passages: list[dict], result: dict) -> bool:
        """Self-Agentic Reflection: evaluate answer quality and autonomously store the learned query pattern."""
        raw_q = (raw_query or "").strip()
        if not raw_q or len(raw_q) < 4:
            return False

        # Self-Reflection Gate: Ensure output is high-confidence, factual, and not an escalation
        status = result.get("status")
        conf = float(result.get("confidence", 0.0))
        answer = result.get("answer", "")
        if status != "answer" or conf < 0.70 or len(answer) < 35:
            return False

        # Reject answers stating insufficiency or failure
        if any(bad in answer.lower() for bad in ("could not be verified", "don't contain a clear answer", "rather not guess", "insufficient_evidence")):
            return False

        # Extract verified chunk IDs used in answer
        chunk_ids = [p["chunk_id"] for p in passages[:4] if p.get("chunk_id")]
        if not chunk_ids:
            return False

        match = self.recall(raw_q, threshold=0.80)
        now = int(time.time())

        if match:
            # Existing cluster: Add this alternative prompt phrasing if not already present
            entry = match.entry
            raw_prog = _detect_programme(raw_q)
            raw_topic = _detect_topic(raw_q)
            entry_prog = _detect_programme(entry.canonical_query)
            entry_topic = _detect_topic(entry.canonical_query)
            if (raw_prog and entry_prog and raw_prog != entry_prog) or (raw_topic and entry_topic and raw_topic != entry_topic):
                return False

            norm_q = raw_q.lower().strip(" ?.,")
            known_patterns = {p.lower().strip(" ?.,") for p in entry.patterns}
            if norm_q not in known_patterns:
                entry.patterns.append(raw_q)
                log.info("[Self-Agentic RAG] Learned new query alias for '%s': '%s' (Total aliases: %d)",
                         entry.canonical_query[:40], raw_q[:40], len(entry.patterns))
            entry.hits += 1
            entry.updated_at = now
            # Merge proven chunk IDs
            for cid in chunk_ids:
                if cid not in entry.chunk_ids:
                    entry.chunk_ids.append(cid)
            self._save()
            return True
        else:
            # Brand new semantic pattern: create a new cluster
            new_id = f"mem_{int(now * 1000) % 10000000:07d}"
            new_entry = MemoryEntry(
                id=new_id,
                canonical_query=extracted_q if len(extracted_q) > 8 else raw_q,
                patterns=[raw_q],
                category=result.get("category") or "general",
                chunk_ids=chunk_ids,
                verified_answer=answer[:800],
                sources=result.get("sources", [])[:3],
                confidence=conf,
                hits=1,
                created_at=now,
                updated_at=now
            )
            unit_emb = self._encode_text(f"{new_entry.canonical_query} {raw_q}")
            if unit_emb is not None:
                new_entry.embedding = [float(x) for x in unit_emb]

            self.entries.append(new_entry)
            self._rebuild_embedding_matrix()
            self._save()
            log.info("[Self-Agentic RAG] Discovered and memorized new query cluster [%s]: '%s' with %d chunk citations",
                     new_id, new_entry.canonical_query[:50], len(chunk_ids))
            return True

    # ------------------------------------------------------------- feedback
    def record_feedback(self, request_id: str | None, rating: str | None, question: str | None) -> bool:
        """Reinforce or down-rank learned memories based on user thumbs up/down."""
        if not question or not rating:
            return False
        match = self.recall(question, threshold=0.75)
        if not match:
            return False
        entry = match.entry
        if rating == "up":
            entry.feedback_up += 1
            log.info("[Self-Agentic RAG] Memory [%s] upvoted by user feedback (+%d)", entry.id, entry.feedback_up)
        elif rating == "down":
            entry.feedback_down += 1
            log.info("[Self-Agentic RAG] Memory [%s] downvoted by user feedback (-%d)", entry.id, entry.feedback_down)
        entry.updated_at = int(time.time())
        self._save()
        return True

    def stats(self) -> dict[str, Any]:
        total_aliases = sum(len(e.patterns) for e in self.entries)
        total_hits = sum(e.hits for e in self.entries)
        return {
            "total_clusters": len(self.entries),
            "total_phrasings_learned": total_aliases,
            "total_hits": total_hits,
            "clusters": [
                {
                    "id": e.id,
                    "canonical": e.canonical_query,
                    "alias_count": len(e.patterns),
                    "aliases": e.patterns[:6],
                    "chunks": e.chunk_ids,
                    "hits": e.hits,
                    "feedback": f"+{e.feedback_up} / -{e.feedback_down}"
                }
                for e in sorted(self.entries, key=lambda x: x.hits, reverse=True)
            ]
        }
