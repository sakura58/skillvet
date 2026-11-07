import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from skillvet.frontmatter import FrontmatterError, split


class SplitTests(unittest.TestCase):
    def test_without_frontmatter(self):
        meta, body, start = split("# Title\n\nText\n")
        self.assertIsNone(meta)
        self.assertEqual(body, "# Title\n\nText\n")
        self.assertEqual(start, 1)

    def test_basic_mapping(self):
        meta, body, start = split("---\nname: demo\ndescription: Use when x\n---\n\nBody\n")
        self.assertEqual(meta, {"name": "demo", "description": "Use when x"})
        self.assertEqual(body, "\nBody\n")
        self.assertEqual(start, 5)

    def test_crlf(self):
        meta, body, start = split("---\r\nname: demo\r\n---\r\nBody\r\n")
        self.assertEqual(meta, {"name": "demo"})
        self.assertEqual(body, "Body\r\n")
        self.assertEqual(start, 4)

    def test_literal_block(self):
        text = "---\ndescription: |\n  line one\n  line two\nname: demo\n---\nbody\n"
        meta, body, start = split(text)
        self.assertEqual(meta["description"], "line one\nline two")
        self.assertEqual(meta["name"], "demo")
        self.assertEqual(body, "body\n")

    def test_folded_block(self):
        text = "---\ndescription: >\n  line one\n  line two\nname: demo\n---\nbody\n"
        meta, _, _ = split(text)
        self.assertEqual(meta["description"], "line one line two")

    def test_quoted_values(self):
        text = '---\ndescription: "Use when a: b"\nname: \'demo\'\n---\n'
        meta, _, _ = split(text)
        self.assertEqual(meta["description"], "Use when a: b")
        self.assertEqual(meta["name"], "demo")

    def test_single_quote_escape(self):
        meta, _, _ = split("---\ndescription: 'it''s fine'\n---\n")
        self.assertEqual(meta["description"], "it's fine")

    def test_comments_are_ignored(self):
        meta, _, _ = split("---\n# a comment\nname: demo\n---\n")
        self.assertEqual(meta, {"name": "demo"})

    def test_missing_closing_fence(self):
        with self.assertRaises(FrontmatterError):
            split("---\nname: demo\nbody\n")

    def test_malformed_line(self):
        with self.assertRaises(FrontmatterError):
            split("---\nname demo\n---\n")

    def test_duplicate_key(self):
        with self.assertRaises(FrontmatterError):
            split("---\nname: a\nname: b\n---\n")

    def test_bom_is_stripped(self):
        meta, _, _ = split("\ufeff---\nname: demo\n---\n")
        self.assertEqual(meta, {"name": "demo"})


if __name__ == "__main__":
    unittest.main()
