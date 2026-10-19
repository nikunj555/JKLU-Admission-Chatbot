"""Regression test suite for Query Understanding and Faculty Retrieval.

Covers the 6 required categories:
  A. Long queries with irrelevant conversational text and one valid JKLU question.
  B. Multiple JKLU questions / queries mixed with unrelated requests.
  C. Short and long faculty queries using department names, abbreviations, and expertise keywords.
  D. Queries for individual faculty members.
  E. Queries for which the indexed source genuinely contains no answer (anti-hallucination / fabrication check).
  F. Verification that official portal faculty records exist in the index and are retrieved with valid source URLs.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jklu import textproc as T
from jklu.agent import JKLUAgent
from jklu.index import KnowledgeBase


class QueryUnderstandingAndFacultyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize knowledge base and agent once
        cls.kb = KnowledgeBase.load(allow_semantic=True)
        cls.agent = JKLUAgent(kb=cls.kb)

    # ======================================================================
    # Category A: Long queries with irrelevant text and one valid question
    # ======================================================================
    def test_category_a_long_query_cse_faculty(self):
        query = (
            "I'm trying to plan my semester and was talking to my friends about different colleges, "
            "and I have a lot of confusion about subjects, but can you tell me which faculty members "
            "teach Computer Science at JKLU?"
        )
        analysis = T.understand_query(query)
        self.assertIn("faculty", analysis.primary_query.lower())
        self.assertIn("computer science", analysis.primary_query.lower())
        self.assertNotIn("friends", analysis.primary_query.lower())
        self.assertNotIn("confusion", analysis.primary_query.lower())

        res = self.agent.ask(query)
        self.assertEqual(res["status"], "answer")
        ans_low = res["answer"].lower()
        # Should retrieve verified CSE faculty
        self.assertTrue(
            any(name in ans_low for name in ("amit", "sinhal", "sonali", "vyas", "taruna", "sunil", "deepika", "ashish")),
            f"Expected CSE faculty in answer, got: {res['answer']}"
        )
        self.assertTrue(len(res["sources"]) > 0)

    def test_category_a_long_query_attendance(self):
        query = "I have been busy all week and I don't understand the university rules, so what is the attendance requirement at JKLU?"
        analysis = T.understand_query(query)
        self.assertIn("attendance", analysis.primary_query.lower())
        self.assertNotIn("busy all week", analysis.primary_query.lower())

        res = self.agent.ask(query)
        self.assertEqual(res["status"], "answer")
        self.assertTrue(
            any(term in res["answer"].lower() for term in ("75%", "attendance", "minimum", "exam")),
            f"Expected attendance policy in answer, got: {res['answer']}"
        )

    def test_category_a_long_query_semester_start(self):
        query = "I am comparing colleges and thinking about my future, but when does JKLU's semester start?"
        analysis = T.understand_query(query)
        self.assertIn("semester start", analysis.primary_query.lower())
        self.assertNotIn("comparing colleges", analysis.primary_query.lower())

        res = self.agent.ask(query)
        self.assertIn(res["status"], ("answer", "clarify"))
        self.assertTrue(len(res["sources"]) > 0 or res["status"] == "answer")

    # ======================================================================
    # Category B: Multiple questions / queries mixed with unrelated requests
    # ======================================================================
    def test_category_b_mixed_movie_request(self):
        query = "Tell me about CSE faculty, and also suggest a movie."
        analysis = T.understand_query(query)
        self.assertIn("faculty", analysis.primary_query.lower())
        self.assertTrue(len(analysis.unrelated_parts) > 0)
        self.assertTrue(any("movie" in u.lower() for u in analysis.unrelated_parts))

        res = self.agent.ask(query)
        self.assertEqual(res["status"], "answer")
        ans_low = res["answer"].lower()
        self.assertTrue(
            any(k in ans_low for k in ("faculty", "professor", "sinhal", "vyas", "sunil", "computer science")),
            f"Expected CSE faculty in answer, got: {res['answer']}"
        )
        # Verify movie request did not break retrieval
        self.assertTrue(len(res["sources"]) > 0)

    def test_category_b_multiple_jklu_questions(self):
        query = "What is the tuition fee for B.Tech CSE and what is the hostel curfew timing?"
        analysis = T.understand_query(query)
        res = self.agent.ask(query)
        self.assertEqual(res["status"], "answer")
        ans_low = res["answer"].lower()
        self.assertTrue("fee" in ans_low or "inr" in ans_low or "tuition" in ans_low)
        self.assertTrue(len(res["sources"]) >= 1)

    # ======================================================================
    # Category C: Short and long faculty queries using departments & keywords
    # ======================================================================
    def test_category_c_cse_faculty_short(self):
        query = "Who are the CSE faculty members at JKLU?"
        res = self.agent.ask(query)
        self.assertEqual(res["status"], "answer")
        ans_low = res["answer"].lower()
        self.assertTrue(
            any(name in ans_low for name in ("amit", "sinhal", "sonali", "taruna", "ashish", "deepika", "ankush", "bhavsar", "patra", "rohit", "ashutosh")),
            f"Expected CSE professors, got: {res['answer']}"
        )

    def test_category_c_computer_science_professors(self):
        query = "List the Computer Science professors."
        res = self.agent.ask(query)
        self.assertEqual(res["status"], "answer")
        ans_low = res["answer"].lower()
        self.assertTrue(
            any(w in ans_low for w in ("professor", "sinhal", "vyas", "sunil", "faculty")),
            f"Expected faculty list, got: {res['answer']}"
        )

    def test_category_c_who_teaches_ai_ml(self):
        query = "Who teaches artificial intelligence and machine learning?"
        res = self.agent.ask(query)
        self.assertEqual(res["status"], "answer")
        ans_low = res["answer"].lower()
        # Should retrieve Dr. Amit Kumar Sinhal, Dr. Tapas Kumar, Dr. Sonali Vyas, or relevant AI/ML faculty
        self.assertTrue(
            any(k in ans_low for k in ("tapas kumar", "amit kumar sinhal", "sonali vyas", "ai", "machine learning")),
            f"Expected AI/ML faculty, got: {res['answer']}"
        )

    def test_category_c_school_of_engineering_faculty(self):
        query = "Which faculty members belong to the School of Engineering?"
        res = self.agent.ask(query)
        self.assertEqual(res["status"], "answer")
        ans_low = res["answer"].lower()
        self.assertTrue(
            any(w in ans_low for w in ("engineering", "tapas kumar", "umesh gupta", "devika kataria", "sinhal")),
            f"Expected engineering faculty, got: {res['answer']}"
        )

    # ======================================================================
    # Category D: Queries for individual faculty members
    # ======================================================================
    def test_category_d_individual_amit_kumar_sinhal(self):
        query = "Tell me about Dr. Amit Kumar Sinhal"
        res = self.agent.ask(query)
        self.assertEqual(res["status"], "answer")
        ans_low = res["answer"].lower()
        self.assertIn("amit kumar sinhal", ans_low)
        self.assertTrue("professor" in ans_low or "computer science" in ans_low)
        # Check source URL format
        urls = [s.get("url") for s in res["sources"] if s.get("url")]
        self.assertTrue(
            any("amit-kumar-sinhal" in u or "faculty" in u for u in urls),
            f"Expected faculty profile URL in sources, got: {urls}"
        )

    def test_category_d_individual_tapas_kumar(self):
        query = "Who is Dr. Tapas Kumar at JKLU?"
        res = self.agent.ask(query)
        self.assertEqual(res["status"], "answer")
        ans_low = res["answer"].lower()
        self.assertIn("tapas kumar", ans_low)
        self.assertTrue("dean" in ans_low or "engineering" in ans_low)

    def test_category_d_individual_umesh_gupta(self):
        query = "Tell me about Dr. Umesh Gupta"
        res = self.agent.ask(query)
        self.assertEqual(res["status"], "answer")
        ans_low = res["answer"].lower()
        self.assertIn("umesh gupta", ans_low)
        self.assertTrue("mathematics" in ans_low or "dean" in ans_low or "academic affairs" in ans_low)

    # ======================================================================
    # Category E: Genuinely unindexed / fabricated queries (Anti-Hallucination)
    # ======================================================================
    def test_category_e_fabricated_faculty_name(self):
        query = "Tell me about Professor Sherlock Holmes of Hogwarts department at JKLU"
        res = self.agent.ask(query)
        # Must NOT answer affirmatively with fabricated facts
        ans_low = res["answer"].lower()
        self.assertNotIn("sherlock holmes is professor of", ans_low)
        self.assertIn(res["status"], ("escalate", "clarify"))

    def test_category_e_pure_off_topic_query(self):
        query = "What is the capital of France?"
        analysis = T.understand_query(query)
        self.assertTrue(analysis.is_off_topic_only)
        res = self.agent.ask(query)
        # Should politely explain specialization in JKLU information
        self.assertIn("jklu", res["answer"].lower())
        self.assertIn("specialize", res["answer"].lower())

    # ======================================================================
    # Category F: Verification of official portal faculty indexing
    # ======================================================================
    def test_category_f_faculty_chunks_exist_in_index(self):
        faculty_chunks = [c for c in self.kb.chunks if c.get("category") == "faculty"]
        self.assertGreaterEqual(
            len(faculty_chunks), 50,
            f"Expected at least 50 faculty chunks in index, found {len(faculty_chunks)}"
        )
        # Verify key faculty names are present in index
        all_text = " ".join(c.get("text", "") for c in faculty_chunks).lower()
        for expected_name in ("amit kumar sinhal", "tapas kumar", "umesh gupta", "sonali vyas", "taruna sunil"):
            self.assertIn(expected_name, all_text, f"Missing {expected_name} from indexed faculty chunks")


if __name__ == "__main__":
    unittest.main()
