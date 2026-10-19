"""Offline tests. Run with:  python run.py --selftest   (or  python -m unittest discover tests)"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jklu import config as C  # noqa: E402
from jklu import evidence as E  # noqa: E402
from jklu import sources as S  # noqa: E402
from jklu import textproc as T  # noqa: E402
from jklu.chunking import chunk_document  # noqa: E402
from jklu.index import BM25, HashingEmbedder, VectorIndex  # noqa: E402
from jklu.ingest import extract_html, extract_pdf, make_doc, remove_boilerplate  # noqa: E402


def _cf(addr: str, key: int = 0x4F) -> str:
    return f"{key:02x}" + "".join(f"{ord(c) ^ key:02x}" for c in addr)


HTML = f"""<html><head><title>Fee Structure | JKLU</title></head><body>
<nav>Home About Contact</nav><main><h1>Fee Structure</h1><p>Fees for Academic Year 2026-27.</p>
<table><tr><th>Programme</th><th>Annual Fee</th></tr><tr><td>B.Tech</td><td>2,84,000</td></tr>
<tr><td>M.Tech</td><td>1,80,000</td></tr></table>
<p>Write to <a href="/cdn-cgi/l/email-protection#{_cf('admissions@jklu.edu.in')}"><span class="__cf_email__"
data-cfemail="{_cf('admissions@jklu.edu.in')}">[email&#160;protected]</span></a></p>
<a href="/admissions/eligibility">Eligibility</a><a href="/files/guide.pdf">Guide</a></main>
<footer>footer junk</footer></body></html>""".encode()


class TextProcTests(unittest.TestCase):
    def test_program_names_normalised(self):
        self.assertEqual(T.tokens("Bachelor of Technology"), T.tokens("B.Tech"))
        self.assertIn("mdes", T.tokens("M.Des fees"))

    def test_routing(self):
        self.assertEqual(T.route_categories("hostel visitors")[0], "hostel")
        self.assertIn("fees", T.route_categories("what is the tuition fee"))
        self.assertEqual(T.route_categories("Who won the FIFA World Cup?"), [])
        # Regression: contact questions must route to contact BEFORE admission
        self.assertEqual(T.route_categories("What is the phone number of the Registrar?")[0], "contact")
        self.assertEqual(T.route_categories("How can I contact the admissions office?")[0], "contact")
        self.assertIn("contact", T.route_categories("What is the email address of the university?"))
        self.assertIn("general", T.route_categories("What are the campus facilities and amenities?"))


class SourceTests(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(S.classify("https://jklu.edu.in/uploads/images/Fee_Refund_Policy_2026.pdf"), "fees")
        self.assertEqual(S.classify("https://jklu.edu.in/admissions/entrance-exams"), "admission")
        self.assertEqual(S.classify("https://jklu.edu.in/x/Hostel-Life-Policy.pdf"), "hostel")
        self.assertEqual(S.classify("https://jklu.edu.in/faculty/dr-sharma"), "faculty")
        self.assertEqual(S.classify("https://jklu.edu.in"), "general")

    def test_follow_rules(self):
        self.assertTrue(S.should_follow("https://jklu.edu.in/faculty/some-person"))
        self.assertFalse(S.should_follow("https://jklu.edu.in/blog/some-post"))
        self.assertFalse(S.should_follow("https://example.com/admissions"))
        self.assertTrue(S.should_follow("https://jklu.edu.in/admissions/lateral-entry"))
        self.assertFalse(S.should_follow("https://applications.jklu.edu.in/"))

    def test_seeds_valid(self):
        for seed in S.SEEDS:
            self.assertIn(seed.category, C.CATEGORIES)
            self.assertTrue(seed.candidates)


class HtmlTests(unittest.TestCase):
    def setUp(self):
        self.res = extract_html(HTML, "https://jklu.edu.in/admissions/fee-structure")
        self.text = "\n".join(self.res["lines"])

    def test_table_rows_are_self_contained(self):
        self.assertIn("Programme: B.Tech; Annual Fee: 2,84,000", self.text)

    def test_cloudflare_email_decoded(self):
        self.assertIn("admissions@jklu.edu.in", self.text)
        self.assertNotIn("protected", self.text)

    def test_nav_footer_removed_and_links_found(self):
        self.assertNotIn("footer junk", self.text)
        urls = [u for u, _ in self.res["links"]]
        self.assertIn("https://jklu.edu.in/admissions/eligibility", urls)
        self.assertIn("https://jklu.edu.in/files/guide.pdf", urls)

    def test_heading_marked(self):
        self.assertIn("# Fee Structure", self.res["lines"])


class PdfTests(unittest.TestCase):
    def test_pdf_roundtrip(self):
        try:
            import pymupdf as fitz
        except Exception:
            import fitz
        doc = fitz.open()
        for i in range(5):
            page = doc.new_page()
            page.insert_text((72, 40), "JKLU Header Line", fontsize=9)
            page.insert_text((72, 120), f"Visitors are allowed only in the visiting area on day {i} of the term in room {i * 7}.", fontsize=11)
            page.insert_text((72, 780), f"{i + 1}", fontsize=9)
        data = doc.tobytes()
        pages = extract_pdf(data)
        self.assertEqual(len(pages), 5)
        flat = " ".join(l for _, ls in pages for l in ls)
        self.assertIn("Visitors are allowed", flat)
        self.assertNotIn("JKLU Header Line", flat)       # repeated header stripped


class ChunkTests(unittest.TestCase):
    def _doc(self, n_sent=120):
        text = "\n".join([f"# Section {i // 30}" if i % 30 == 0 else
                          f"This is sentence number {i} about hostel rules and timings for students." for i in range(n_sent)])
        return make_doc("https://jklu.edu.in/x", "hostel", "Hostel Policy", "html", [(None, text.split("\n"))])

    def test_chunk_size_and_metadata(self):
        chunks = chunk_document(self._doc())
        self.assertGreater(len(chunks), 3)
        for c in chunks:
            self.assertLessEqual(c["n_words"], int(C.CHUNK_WORDS * 1.35))
            self.assertEqual(c["category"], "hostel")
            self.assertTrue(c["section"].startswith("Section"))

    def test_overlap_and_ids_unique(self):
        chunks = chunk_document(self._doc())
        self.assertEqual(len({c["chunk_id"] for c in chunks}), len(chunks))

    def test_boilerplate_removal(self):
        docs = []
        for i in range(8):
            lines = ["Menu Eligibility Fee Structure", f"Unique content number {i} " + "word " * 20]
            docs.append(make_doc(f"https://jklu.edu.in/admissions/p{i}", "admission", f"P{i}", "html", [(None, lines)]))
        remove_boilerplate(docs)
        self.assertNotIn("Menu Eligibility", " ".join(t for d in docs for _, t in d["pages"]))


class RetrievalTests(unittest.TestCase):
    def test_bm25_ranks_relevant_first(self):
        docs = ["hostel visitors rules and timings", "tuition fee for btech programme", "scholarship for jee main"]
        bm = BM25(docs)
        self.assertEqual(bm.top(T.content_terms("btech tuition fee"), 3)[0][0], 1)

    def test_faiss_or_numpy_index(self):
        emb = HashingEmbedder()
        texts = ["hostel visitors rules", "tuition fee structure", "scholarship criteria"]
        vi = VectorIndex.build(emb.encode(texts))
        _, ids = vi.search(emb.encode(["what are the visitor rules in the hostel"])[0], 1)
        self.assertEqual(int(ids[0]), 0)


class EvidenceTests(unittest.TestCase):
    def _search(self, text, q, routed=("fees",), dense=None):
        return {"results": [{"text": text, "title": "Fee Structure", "section": "", "dense_score": dense}],
                "terms": T.content_terms(q), "semantic": dense is not None, "routed": list(routed)}

    def test_answer_when_covered(self):
        q = "What is the tuition fee for B.Tech?"
        ev = E.check(q, self._search("Tuition fee for Bachelor of Technology is 2,84,000", q))
        self.assertEqual(ev.status, E.ANSWER)

    def test_clarify_generic(self):
        ev = E.check("What is the fee?", self._search("Tuition fee 2,84,000", "fee"))
        self.assertEqual(ev.status, E.CLARIFY)
        self.assertTrue(ev.clarification)

    def test_escalate_unsupported_year(self):
        q = "What will be the hostel fee in 2030?"
        ev = E.check(q, self._search("Hostel fee for Academic Year 2026-27 is 1,00,000", q, routed=("hostel", "fees")))
        self.assertEqual(ev.status, E.ESCALATE)

    def test_escalate_off_topic(self):
        q = "Who won the FIFA World Cup?"
        ev = E.check(q, self._search("Students may participate in sports and world class facilities", q, routed=()))
        self.assertEqual(ev.status, E.ESCALATE)


class AgentTests(unittest.TestCase):
    """End-to-end on the project's own knowledge base (built on demand)."""

    @classmethod
    def setUpClass(cls):
        from jklu.agent import JKLUAgent
        from jklu.index import ensure_index
        if not C.CHUNKS_PATH.is_file():
            from jklu.ingest import run_ingestion
            run_ingestion(offline=True)
        ensure_index()
        cls.agent = JKLUAgent()

    def test_answers_with_sources(self):
        r = self.agent.ask("What is the annual academic fee for B.Tech?")
        self.assertEqual(r["status"], "answer")
        self.assertTrue(r["sources"])

    def test_rejects_irrelevant(self):
        r = self.agent.ask("Who won the FIFA World Cup?")
        self.assertEqual(r["status"], "escalate")

    def test_clarifies_vague(self):
        self.assertEqual(self.agent.ask("What is the fee?")["status"], "clarify")

    def test_clarify_has_suggestion_chips(self):
        r = self.agent.ask("What is the fee?")
        self.assertTrue(r["suggestions"] and {"label", "question"} <= set(r["suggestions"][0]))

    def test_escalate_has_structured_contacts(self):
        r = self.agent.ask("What will be the hostel fee in 2030?")
        self.assertEqual(r["status"], "escalate")
        self.assertIsInstance(r["contacts"], list)
        self.assertTrue(r["contact_page"].startswith("https://"))

    def test_suggested_questions_are_not_misrouted(self):
        """Regression: UI suggestion cards must reach retrieval (not small-talk / false 'too general')."""
        for q in ["Help me understand the scholarship process.", "How do I contact the university?",
                  "What are the admission requirements?", "Where can I find the academic calendar?",
                  "Where can I find examination regulations?"]:
            self.assertEqual(self.agent.ask(q)["status"], "answer", q)

    def test_every_response_has_request_id(self):
        self.assertTrue(self.agent.ask("What is the fee?")["request_id"])

    def test_greeting_and_empty(self):
        self.assertEqual(self.agent.ask("hello")["status"], "smalltalk")
        self.assertEqual(self.agent.ask("   ")["status"], "clarify")

    def test_followup_uses_history(self):
        hist = [{"role": "user", "content": "What is the tuition fee for B.Tech?"},
                {"role": "assistant", "content": "..."}]
        r = self.agent.ask("and for M.Tech?", history=hist)
        self.assertIn("B.Tech", r["query_used"])


class ApiTests(unittest.TestCase):
    """HTTP contract used by the React UI (skipped when fastapi's test client dependencies are missing)."""

    @classmethod
    def setUpClass(cls):
        try:
            from fastapi.testclient import TestClient
            from jklu import api
        except Exception as exc:  # pragma: no cover
            raise unittest.SkipTest(f"fastapi test client unavailable: {exc}")
        cls.api = api
        cls.client = TestClient(api.app)

    def test_health_and_aliases(self):
        for path in ("/health", "/api/health"):
            self.assertEqual(self.client.get(path).json()["status"], "ok")
        self.assertIn("categories", self.client.get("/api/categories").json())

    def test_chat_contract(self):
        r = self.client.post("/api/chat", json={"question": "What is the tuition fee for B.Tech?"}).json()
        for key in ("status", "answer", "sources", "suggestions", "contacts", "contact_page", "request_id"):
            self.assertIn(key, r)
        self.assertEqual(self.client.post("/api/chat", json={"question": ""}).status_code, 422)

    def test_feedback_validation_and_storage(self):
        import tempfile
        from pathlib import Path
        self.api.FEEDBACK_PATH = Path(tempfile.mkdtemp()) / "feedback.jsonl"
        self.assertEqual(self.client.post("/api/feedback", json={}).status_code, 422)
        self.assertEqual(self.client.post("/api/feedback", json={"rating": "meh"}).status_code, 422)
        ok = self.client.post("/api/feedback", json={"rating": "up", "request_id": "abc", "status": "answer"})
        self.assertTrue(ok.json()["ok"])
        self.assertIn('"rating": "up"', self.api.FEEDBACK_PATH.read_text(encoding="utf-8"))

    def test_ui_is_served(self):
        self.assertEqual(self.client.get("/").status_code, 200)


if __name__ == "__main__":
    unittest.main()
