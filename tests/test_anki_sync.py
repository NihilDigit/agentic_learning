import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "alfsrs" / "scripts" / "anki_sync.py"
SPEC = importlib.util.spec_from_file_location("anki_sync", SCRIPT)
anki_sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(anki_sync)


class AnkiSyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.course = Path(self.tmp.name) / "course"
        (self.course / "anki_cards").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def write_cards(self, text):
        (self.course / "anki_cards" / "cards.md").write_text(text, encoding="utf-8")

    def test_malformed_card_fails_instead_of_being_skipped(self):
        self.write_cards("<!-- id: k1.01 -->\n没有 Q/A")

        with self.assertRaises(anki_sync.CardParseError):
            anki_sync.parse_cards(self.course)

    def test_duplicate_card_id_fails(self):
        self.write_cards(
            "<!-- id: k1.01 -->\nQ: one\nA: a\n\n<!-- id: k1.01 -->\nQ: two\nA: b\n"
        )

        with self.assertRaisesRegex(anki_sync.CardParseError, "重复"):
            anki_sync.parse_cards(self.course)

    def test_resolve_deck_uses_documented_courses_schema(self):
        courses_file = self.course.parent / "courses.json"
        courses_file.write_text(
            json.dumps(
                {
                    "active": "course",
                    "courses": {"course": {"title": "测试课程"}},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        self.assertEqual(anki_sync.resolve_deck(self.course), "测试课程")

    def test_sync_adds_and_removes_tags_to_match_markdown(self):
        note = {
            "noteId": 42,
            "fields": {
                "CardID": {"value": "k1.01"},
                "Q": {"value": "question"},
                "A": {"value": "answer"},
            },
            "tags": ["keep", "remove"],
        }
        calls = []

        def fake_rpc(action, **params):
            calls.append((action, params))
            responses = {
                "version": 6,
                "modelNames": [anki_sync.MODEL],
                "createDeck": 1,
                "findNotes": [42],
                "notesInfo": [note],
                "addTags": None,
                "removeTags": None,
            }
            return responses[action]

        cards = [
            {
                "id": "k1.01",
                "q": "question",
                "a": "answer",
                "tags": ["keep", "add"],
                "src": "cards.md",
            }
        ]
        with patch.object(anki_sync, "rpc", side_effect=fake_rpc):
            result = anki_sync.sync_cards("deck", cards)

        self.assertEqual(result["unchanged"], 1)
        self.assertIn(("addTags", {"notes": [42], "tags": "add"}), calls)
        self.assertIn(("removeTags", {"notes": [42], "tags": "remove"}), calls)

    def test_duplicate_card_id_in_anki_fails_before_updates(self):
        notes = [
            {"noteId": 1, "fields": {"CardID": {"value": "k1.01"}}, "tags": []},
            {"noteId": 2, "fields": {"CardID": {"value": "k1.01"}}, "tags": []},
        ]

        def fake_rpc(action, **_params):
            responses = {
                "version": 6,
                "modelNames": [anki_sync.MODEL],
                "createDeck": 1,
                "findNotes": [1, 2],
                "notesInfo": notes,
            }
            return responses[action]

        with (
            patch.object(anki_sync, "rpc", side_effect=fake_rpc),
            self.assertRaisesRegex(RuntimeError, "重复 CardID"),
        ):
            anki_sync.sync_cards("deck", [])


if __name__ == "__main__":
    unittest.main()
