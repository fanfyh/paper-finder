from __future__ import annotations

import unittest

from codex_research_assist.html_fmt import format_digest_html
from codex_research_assist.review_digest import build_system_review


class ReviewDigestTest(unittest.TestCase):
    def test_build_system_review_exposes_digest_fields(self) -> None:
        candidate = {
            "paper": {
                "title": "Bilevel PINN optimization for constrained PDEs",
                "abstract": "We study bilevel optimization for physics-informed neural networks. The method improves stability.",
                "identifiers": {"arxiv_id": "2501.12345", "url": "https://arxiv.org/abs/2501.12345"},
            },
            "triage": {"matched_interest_labels": ["PINN", "Bilevel Optimization"]},
            "_scores": {"total": 0.84, "map_match": 0.91, "zotero_semantic": 0.73},
            "review": {
                "review_status": "pending",
                "reviewer_summary": None,
                "zotero_comparison": None,
                "recommendation": "unset",
            },
        }

        review = build_system_review(candidate, profile={"profile_id": "demo"})
        self.assertEqual(review["review_status"], "system_generated")
        self.assertEqual(review["recommendation"], "read_first")
        self.assertIn("Matches multiple active profile interests", review["why_it_matters"])
        self.assertIn("Zotero comparison has not been run", review["caveats"][0] + " ".join(review["caveats"][1:]))
        self.assertTrue(review["quick_takeaways"])

    def test_format_digest_html_renders_review_sections(self) -> None:
        candidate = {
            "paper": {
                "title": "A paper",
                "abstract": "Short abstract.",
                "authors": ["Alice", "Bob"],
                "identifiers": {"arxiv_id": "2501.12345", "url": "https://arxiv.org/abs/2501.12345"},
            },
            "triage": {"matched_interest_labels": ["PINN"]},
            "_scores": {
                "total": 0.8,
                "map_match": 0.8,
                "zotero_semantic": 0.6,
                "semantic_top_title": "Nearest Zotero Paper",
            },
            "review": {
                "recommendation": "read_first",
                "why_it_matters": "Matches your active profile interest in PINN.",
                "reviewer_summary": "Short abstract.",
                "zotero_comparison": {
                    "status": "matched",
                    "summary": "Closest to PINN optimization papers already in Zotero.",
                    "related_items": [
                        {"title": "Nearest Zotero Paper", "item_key": "ABCD1234", "relation": "semantic neighbor"}
                    ],
                },
                "quick_takeaways": ["Recommendation: Read First", "Matched interests: PINN"],
                "caveats": ["Zotero comparison has not been run in digest mode yet."],
            },
        }

        html = format_digest_html([candidate], "2026-03-12")
        self.assertIn("Nearest Zotero", html)
        self.assertIn("Nearest Zotero Paper", html)
        self.assertIn("Paper summary", html)
        self.assertIn("Quick takeaways", html)
        self.assertIn("Caveats", html)
        self.assertIn("M:0.80", html)


if __name__ == "__main__":
    unittest.main()
