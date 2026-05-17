import os
import unittest


class TestIOfficeRagIngest(unittest.TestCase):
  def test_chunk_text_basic(self):
    from app.services.ioffice_rag_ingest import FulltextChunkingConfig, _chunk_text

    cfg = FulltextChunkingConfig(chunk_chars=50, overlap_chars=10, min_chunk_chars=10, max_total_chars=1000)
    text = "A" * 40 + "\n\n" + "B" * 40 + "\n\n" + "C" * 40
    chunks = _chunk_text(text, cfg)
    self.assertIsInstance(chunks, list)
    self.assertTrue(chunks)
    self.assertTrue(all(isinstance(x, str) and x.strip() for x in chunks))

  def test_category_domain_map_parsing(self):
    from app.services.ioffice_rag_ingest import _domains_from_category_ids

    os.environ["EDUAI_RAG_CATEGORY_DOMAIN_MAP"] = "{\"12\": [\"MANAGEMENT\", \"TEACHING\"], \"99\": \"LEARNING\"}"
    domains = _domains_from_category_ids([12, 99])
    self.assertIn("MANAGEMENT", domains)
    self.assertIn("TEACHING", domains)
    self.assertIn("LEARNING", domains)


if __name__ == "__main__":
  unittest.main()
