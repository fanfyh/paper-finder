from __future__ import annotations

import json
import unittest
from pathlib import Path


class ReviewContractSchemaTest(unittest.TestCase):
    def test_candidate_card_review_schema_has_digest_fields(self) -> None:
        path = Path("reports/schema/candidate-card.schema.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        review = payload["properties"]["review"]
        required = set(review["required"])
        self.assertTrue({"why_it_matters", "quick_takeaways", "caveats", "generation"}.issubset(required))
        recommendation_enum = set(review["properties"]["recommendation"]["enum"])
        self.assertIn("read_first", recommendation_enum)
        self.assertIn("skim", recommendation_enum)

    def test_review_patch_schema_exists_and_mentions_agent_mode(self) -> None:
        path = Path("reports/schema/review-patch.schema.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        generation = payload["properties"]["review"]["properties"]["generation"]["properties"]["mode"]["enum"]
        self.assertIn("agent_zotero_fill", generation)


if __name__ == "__main__":
    unittest.main()
