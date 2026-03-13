from __future__ import annotations

import unittest

from codex_research_assist.zotero_mcp.feedback import (
    ALLOWED_DECISIONS,
    build_feedback_note,
    decision_status_tag,
    normalize_feedback_payload,
)
from codex_research_assist.zotero_mcp.client import ZoteroClient


class AllowedDecisionsTest(unittest.TestCase):
    def test_feedback_decisions_cover_review_recommendations(self) -> None:
        review_recommendations = {"read_first", "skim", "watch", "skip_for_now", "archive", "watchlist", "ignore", "unset"}
        self.assertTrue(review_recommendations.issubset(ALLOWED_DECISIONS))

    def test_skim_and_skip_for_now_are_allowed(self) -> None:
        self.assertIn("skim", ALLOWED_DECISIONS)
        self.assertIn("skip_for_now", ALLOWED_DECISIONS)
        self.assertIn("watchlist", ALLOWED_DECISIONS)


class DecisionStatusTagTest(unittest.TestCase):
    def test_archive_tag(self) -> None:
        self.assertEqual(decision_status_tag("archive"), "ra-status:archive")

    def test_read_first_tag(self) -> None:
        self.assertEqual(decision_status_tag("read_first"), "ra-status:read_first")

    def test_skim_tag(self) -> None:
        self.assertEqual(decision_status_tag("skim"), "ra-status:skim")

    def test_skip_for_now_tag(self) -> None:
        self.assertEqual(decision_status_tag("skip_for_now"), "ra-status:skip_for_now")

    def test_watchlist_tag(self) -> None:
        self.assertEqual(decision_status_tag("watchlist"), "ra-status:watchlist")

    def test_unset_returns_none(self) -> None:
        self.assertIsNone(decision_status_tag("unset"))

    def test_whitespace_is_stripped(self) -> None:
        self.assertEqual(decision_status_tag("  archive  "), "ra-status:archive")


class NormalizeFeedbackPayloadTest(unittest.TestCase):
    def _base_payload(self, decision: str = "archive") -> dict:
        return {
            "source": "test",
            "decisions": [
                {
                    "match": {"doi": "10.1000/test"},
                    "decision": decision,
                    "rationale": "test rationale",
                    "add_tags": [],
                    "remove_tags": [],
                    "add_collections": [],
                    "remove_collections": [],
                    "note_append": "",
                }
            ],
        }

    def test_normalize_accepts_all_decision_types(self) -> None:
        for decision in ALLOWED_DECISIONS:
            payload = self._base_payload(decision)
            result = normalize_feedback_payload(payload)
            self.assertEqual(result["decisions"][0]["decision"], decision)

    def test_rejects_invalid_decision(self) -> None:
        payload = self._base_payload("definitely_invalid")
        with self.assertRaises(ValueError):
            normalize_feedback_payload(payload)

    def test_deduplicates_tags(self) -> None:
        payload = self._base_payload()
        payload["decisions"][0]["add_tags"] = ["survey", "Survey", "SURVEY"]
        result = normalize_feedback_payload(payload)
        self.assertEqual(result["decisions"][0]["add_tags"], ["survey"])

    def test_requires_at_least_one_match_field(self) -> None:
        payload = self._base_payload()
        payload["decisions"][0]["match"] = {}
        with self.assertRaises(ValueError):
            normalize_feedback_payload(payload)

    def test_match_by_item_key(self) -> None:
        payload = self._base_payload()
        payload["decisions"][0]["match"] = {"item_key": "ABC123"}
        result = normalize_feedback_payload(payload)
        self.assertEqual(result["decisions"][0]["match"]["item_key"], "ABC123")

    def test_match_by_title_contains(self) -> None:
        payload = self._base_payload()
        payload["decisions"][0]["match"] = {"title_contains": "physics-informed"}
        result = normalize_feedback_payload(payload)
        self.assertEqual(result["decisions"][0]["match"]["title_contains"], "physics-informed")

    def test_doi_is_lowercased(self) -> None:
        payload = self._base_payload()
        payload["decisions"][0]["match"] = {"doi": "10.1000/ABC"}
        result = normalize_feedback_payload(payload)
        self.assertEqual(result["decisions"][0]["match"]["doi"], "10.1000/abc")

    def test_generated_at_auto_filled(self) -> None:
        payload = self._base_payload()
        result = normalize_feedback_payload(payload)
        self.assertTrue(result["generated_at"])

    def test_empty_decisions_rejected(self) -> None:
        with self.assertRaises(ValueError):
            normalize_feedback_payload({"decisions": []})


class BuildFeedbackNoteTest(unittest.TestCase):
    def test_note_contains_decision_and_rationale(self) -> None:
        decision = {
            "decision": "read_first",
            "rationale": "High fit to profile.",
            "note_append": "promote",
            "add_tags": ["survey"],
            "remove_tags": ["old"],
            "add_collections": ["Queue"],
            "remove_collections": [],
        }
        note = build_feedback_note(decision, generated_at="2026-03-13T00:00:00Z", source="test")
        self.assertIn("decision: read_first", note)
        self.assertIn("rationale: High fit to profile.", note)
        self.assertIn("note: promote", note)
        self.assertIn("add_tags: survey", note)
        self.assertIn("remove_tags: old", note)
        self.assertIn("add_collections: Queue", note)

    def test_note_omits_empty_fields(self) -> None:
        decision = {
            "decision": "watch",
            "rationale": "Mild interest.",
            "note_append": "",
            "add_tags": [],
            "remove_tags": [],
            "add_collections": [],
            "remove_collections": [],
        }
        note = build_feedback_note(decision, generated_at="2026-03-13T00:00:00Z", source="test")
        self.assertNotIn("note:", note)
        self.assertNotIn("add_tags:", note)


class _FakeZotero:
    def __init__(self) -> None:
        self.items = {
            "ABC123": {
                "data": {
                    "key": "ABC123",
                    "itemType": "journalArticle",
                    "title": "Physics-informed transformers",
                    "DOI": "10.1000/test",
                    "tags": [{"tag": "old-tag"}, {"tag": "ra-status:watch"}],
                    "collections": ["COLL-EXISTING"],
                }
            }
        }
        self.collections_payload = [
            {"data": {"key": "COLL-EXISTING", "name": "Existing", "parentCollection": False}},
        ]
        self.created_collections: list[list[dict[str, str]]] = []
        self.updated_items: list[str] = []
        self.created_notes: list[dict[str, str]] = []

    def top(self) -> list[dict]:
        return list(self.items.values())

    def item(self, item_key: str) -> dict:
        return self.items[item_key]

    def collections(self) -> list[dict]:
        return list(self.collections_payload)

    def create_collections(self, payload: list[dict[str, str]]) -> dict:
        self.created_collections.append(payload)
        key = f"COLL-{len(self.created_collections)}"
        name = payload[0]["name"]
        self.collections_payload.append({"data": {"key": key, "name": name, "parentCollection": False}})
        return {"successful": {"0": {"data": {"key": key, "name": name}}}}

    def update_item(self, entry: dict) -> None:
        self.updated_items.append(entry["data"]["key"])

    def item_template(self, item_type: str) -> dict:
        if item_type != "note":
            raise AssertionError(f"unexpected template type: {item_type}")
        return {"itemType": "note", "note": "", "parentItem": ""}

    def create_items(self, items: list[dict]) -> dict:
        self.created_notes.extend(items)
        return {"successful": {"0": {"key": "NOTE1"}}}


class ApplyFeedbackTest(unittest.TestCase):
    def _client(self) -> tuple[ZoteroClient, _FakeZotero]:
        zot = _FakeZotero()
        client = ZoteroClient.__new__(ZoteroClient)
        client.zot = zot
        client._collections_cache = None
        return client, zot

    def test_dry_run_does_not_create_missing_collections(self) -> None:
        client, zot = self._client()
        payload = normalize_feedback_payload(
            {
                "source": "test",
                "decisions": [
                    {
                        "match": {"item_key": "ABC123"},
                        "decision": "archive",
                        "rationale": "file it",
                        "add_tags": ["queue"],
                        "remove_tags": [],
                        "add_collections": ["Archive"],
                        "remove_collections": [],
                        "note_append": "",
                    }
                ],
            }
        )

        result = client.apply_feedback(payload, dry_run=True)

        self.assertEqual(zot.created_collections, [])
        self.assertEqual(zot.updated_items, [])
        self.assertEqual(zot.created_notes, [])
        self.assertEqual(result["planned"][0]["collections_to_create"], ["Archive"])

    def test_unset_is_reported_but_not_written_back(self) -> None:
        client, zot = self._client()
        payload = normalize_feedback_payload(
            {
                "source": "test",
                "decisions": [
                    {
                        "match": {"item_key": "ABC123"},
                        "decision": "unset",
                        "rationale": "no decision yet",
                        "add_tags": [],
                        "remove_tags": [],
                        "add_collections": [],
                        "remove_collections": [],
                        "note_append": "",
                    }
                ],
            }
        )

        result = client.apply_feedback(payload, dry_run=False)

        self.assertEqual(result["planned"][0]["status"], "skipped_unset")
        self.assertEqual(result["applied"], [])
        self.assertEqual(zot.updated_items, [])
        self.assertEqual(zot.created_notes, [])
        self.assertEqual(zot.created_collections, [])


if __name__ == "__main__":
    unittest.main()
