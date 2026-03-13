from __future__ import annotations

import json
import unittest
from pathlib import Path

from codex_research_assist.review_patch import validate_review_patch
from codex_research_assist.zotero_mcp.feedback import ALLOWED_DECISIONS, normalize_feedback_payload


class SchemaAlignmentTest(unittest.TestCase):
    """Verify that feedback decisions, review recommendations, and JSON schemas stay aligned."""

    def test_feedback_schema_matches_code(self) -> None:
        schema_path = Path("reports/schema/zotero-feedback.schema.json")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema_decisions = set(schema["$defs"]["decision"]["properties"]["decision"]["enum"])
        self.assertEqual(schema_decisions, ALLOWED_DECISIONS)

    def test_review_recommendations_subset_of_feedback_decisions(self) -> None:
        review_recommendations = {
            "read_first", "skim", "watch", "skip_for_now",
            "archive", "watchlist", "ignore", "unset",
        }
        self.assertTrue(
            review_recommendations.issubset(ALLOWED_DECISIONS),
            f"Missing from feedback: {review_recommendations - ALLOWED_DECISIONS}",
        )

    def test_review_patch_recommendations_match_feedback_decisions(self) -> None:
        for decision in ALLOWED_DECISIONS:
            patch = {
                "candidate_id": "test-cand",
                "review": {
                    "review_status": "agent_completed",
                    "reviewer_summary": "Test.",
                    "zotero_comparison": {"status": "not_run", "summary": "n/a", "related_items": []},
                    "recommendation": decision,
                    "why_it_matters": "Test.",
                    "selected_for_digest": True,
                    "quick_takeaways": [],
                    "caveats": [],
                    "generation": {"mode": "agent_zotero_fill", "sources": ["test"]},
                },
            }
            result = validate_review_patch(patch)
            self.assertEqual(result["review"]["recommendation"], decision)

    def test_feedback_payload_round_trip_all_decisions(self) -> None:
        for decision in ALLOWED_DECISIONS:
            payload = {
                "source": "alignment-test",
                "decisions": [
                    {
                        "match": {"doi": "10.1000/test"},
                        "decision": decision,
                        "rationale": f"Testing {decision}",
                        "add_tags": [],
                        "remove_tags": [],
                        "add_collections": [],
                        "remove_collections": [],
                        "note_append": "",
                    }
                ],
            }
            result = normalize_feedback_payload(payload)
            self.assertEqual(result["decisions"][0]["decision"], decision)

    def test_candidate_card_schema_recommendation_covers_feedback(self) -> None:
        schema_path = Path("reports/schema/candidate-card.schema.json")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        card_recommendations = set(schema["properties"]["review"]["properties"]["recommendation"]["enum"])
        self.assertTrue(
            ALLOWED_DECISIONS.issubset(card_recommendations),
            f"Missing from candidate-card schema: {ALLOWED_DECISIONS - card_recommendations}",
        )


if __name__ == "__main__":
    unittest.main()
