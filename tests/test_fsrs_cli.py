import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "al" / "scripts" / "fsrs_cli.py"


class FsrsCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.course = Path(self.tmp.name) / "course"
        modules = self.course / "modules"
        modules.mkdir(parents=True)
        (modules / "1.1.md").write_text("知识点\n题目\n答案\n", encoding="utf-8")
        self.index = {
            "course": "course",
            "next_module": "1.1",
            "modules": [
                {
                    "id": "1.1",
                    "title": "测试模块",
                    "file": "modules/1.1.md",
                    "status": "pending",
                    "has_exercises": True,
                    "wrong": [],
                }
            ],
        }
        self.write_index(self.index)

    def tearDown(self):
        self.tmp.cleanup()

    def write_index(self, value):
        (self.course / "index.json").write_text(
            json.dumps(value, ensure_ascii=False),
            encoding="utf-8",
        )

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(CLI), *args, "--course", str(self.course)],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_invalid_module_does_not_mutate_state(self):
        before = (self.course / "index.json").read_bytes()

        result = self.run_cli("grade", "9.9.01", "again")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("不存在", result.stderr)
        self.assertEqual((self.course / "index.json").read_bytes(), before)
        self.assertFalse((self.course / "cards.json").exists())
        self.assertFalse((self.course / "reviews.jsonl").exists())

    def test_invalid_qid_format_does_not_mutate_state(self):
        before = (self.course / "index.json").read_bytes()

        result = self.run_cli("grade", "1.1.", "again")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("格式错误", result.stderr)
        self.assertEqual((self.course / "index.json").read_bytes(), before)
        self.assertFalse((self.course / "cards.json").exists())

    def test_first_good_requires_explicit_allow_new(self):
        rejected = self.run_cli("grade", "1.1.01", "good")

        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("--allow-new", rejected.stderr)
        self.assertFalse((self.course / "cards.json").exists())

        accepted = self.run_cli("grade", "1.1.01", "good", "--allow-new")

        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        cards = json.loads((self.course / "cards.json").read_text(encoding="utf-8"))
        self.assertIn("1.1.01", cards)

    def test_wrong_answer_then_successful_review_updates_wrong_list(self):
        wrong = self.run_cli("grade", "1.1.02", "again", "--note", "概念错误")
        self.assertEqual(wrong.returncode, 0, wrong.stderr)
        index = json.loads((self.course / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["modules"][0]["wrong"], ["1.1.02"])

        reviewed = self.run_cli("grade", "1.1.02", "good")
        self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
        index = json.loads((self.course / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["modules"][0]["wrong"], [])
        reviews = (
            (self.course / "reviews.jsonl").read_text(encoding="utf-8").splitlines()
        )
        self.assertEqual(len(reviews), 2)

    def test_check_reports_malformed_module_as_json(self):
        self.write_index({"modules": [None]})

        result = self.run_cli("check")

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertIn("modules[0]: 必须是对象", payload["errors"])
        self.assertNotIn("Traceback", result.stderr)

    def test_check_rejects_orphan_card(self):
        (self.course / "cards.json").write_text(
            json.dumps({"9.9.01": {"qid": "9.9.01", "module": "9.9"}}),
            encoding="utf-8",
        )

        result = self.run_cli("check")

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(any("不存在的模块" in error for error in payload["errors"]))


if __name__ == "__main__":
    unittest.main()
