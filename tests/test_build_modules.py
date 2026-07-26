import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "almake" / "examples" / "build_modules.py"
SPEC = importlib.util.spec_from_file_location("build_modules", SCRIPT)
build_modules = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_modules)


class BuildModulesTest(unittest.TestCase):
    def test_generated_outline_points_to_existing_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.pdf"
            writer = PdfWriter()
            for _ in range(6):
                writer.add_blank_page(width=100, height=100)
            with source.open("wb") as f:
                writer.write(f)

            toc = {
                "chapters": [
                    {
                        "num": "1",
                        "page": 1,
                        "sections": [
                            {
                                "num": "1.1",
                                "title": "测试",
                                "page": 1,
                                "subsections": [
                                    {"num": "1.1.1", "title": "试题精选", "page": 2},
                                    {"num": "1.1.2", "title": "答案与解析", "page": 4},
                                ],
                            }
                        ],
                    }
                ],
                "references_page": 6,
            }
            (root / "toc.json").write_text(
                json.dumps(toc, ensure_ascii=False),
                encoding="utf-8",
            )

            previous_cwd = os.getcwd()
            previous_map = build_modules.PDF_MAP
            try:
                os.chdir(root)
                build_modules.PDF_MAP = [(1, 6, "source.pdf", 0)]
                build_modules.readers.clear()
                build_modules.main()
            finally:
                build_modules.PDF_MAP = previous_map
                build_modules.readers.clear()
                os.chdir(previous_cwd)

            result = PdfReader(root / "modules" / "1.1_测试.pdf")
            destinations = [
                result.get_destination_page_number(item) for item in result.outline
            ]
            self.assertEqual(destinations, [0, 2, 4])


if __name__ == "__main__":
    unittest.main()
