import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from skillvet.cli import main

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


class CliTests(unittest.TestCase):
    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_clean_example_passes(self):
        code, out, _ = self.run_main(
            [str(EXAMPLES / "release-notes"), "--fail-on", "warning"]
        )
        self.assertEqual(code, 0)
        self.assertIn("ok", out)

    def test_bad_example_fails(self):
        code, _, _ = self.run_main([str(EXAMPLES / "bad-skill")])
        self.assertEqual(code, 1)

    def test_json_format(self):
        _, out, _ = self.run_main(
            [str(EXAMPLES), "--format", "json", "--fail-on", "none"]
        )
        payload = json.loads(out)
        self.assertEqual(payload["tool"], "skillvet")
        self.assertEqual(payload["summary"]["skills"], 2)
        names = [skill["name"] for skill in payload["skills"]]
        self.assertIn("release-notes", names)

    def test_github_format(self):
        _, out, _ = self.run_main(
            [str(EXAMPLES / "bad-skill"), "--format", "github", "--fail-on", "none"]
        )
        self.assertIn("::error file=", out)
        self.assertIn("title=SEC001", out)

    def test_missing_path(self):
        code, _, err = self.run_main([str(ROOT / "does-not-exist")])
        self.assertEqual(code, 2)
        self.assertIn("no such file", err)

    def test_no_skill_files(self):
        code, _, err = self.run_main([str(ROOT / "src")])
        self.assertEqual(code, 0)
        self.assertIn("no SKILL.md", err)

    def test_min_severity_filters_output(self):
        _, out, _ = self.run_main(
            [
                str(EXAMPLES / "bad-skill"),
                "--min-severity",
                "error",
                "--fail-on",
                "none",
            ]
        )
        self.assertNotIn("DESC002", out)

    def test_min_severity_does_not_change_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "demo"
            directory.mkdir()
            (directory / "SKILL.md").write_text(
                "---\nname: demo\ndescription: Helps.\n---\n# Body\n",
                encoding="utf-8",
            )
            code, out, _ = self.run_main(
                [
                    str(directory),
                    "--min-severity",
                    "error",
                    "--fail-on",
                    "warning",
                ]
            )
        self.assertEqual(code, 1)
        self.assertNotIn("DESC002", out)

    def test_list_rules(self):
        code, out, _ = self.run_main(["--list-rules"])
        self.assertEqual(code, 0)
        self.assertIn("SEC001", out)


if __name__ == "__main__":
    unittest.main()
