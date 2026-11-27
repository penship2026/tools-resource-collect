"""A1 双编译器:契约校验、确定性、预算、注册表与 CLI 冒烟。"""
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "ai-template"))

import compiler  # noqa: E402
import theme_lint  # noqa: E402

LAYOUT = os.path.join(ROOT, "tests/fixtures/specs/layout-news-dense.json")
THEME = os.path.join(ROOT, "tests/fixtures/specs/theme-mist.json")


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class CompilerTest(unittest.TestCase):
    def setUp(self):
        self.layout = load(LAYOUT)
        self.theme = load(THEME)

    def test_layout_rejects_unlanded_capabilities(self):
        for key in ("sidebar", "rails", "timeline", "theme"):
            bad = copy.deepcopy(self.layout)
            bad[key] = True
            self.assertTrue(compiler.validate_layout_spec(bad), key)

    def test_layout_rejects_bad_values(self):
        bad = copy.deepcopy(self.layout)
        bad["hero"]["mainRatio"] = 0.9
        self.assertTrue(compiler.validate_layout_spec(bad))
        bad = copy.deepcopy(self.layout)
        bad["bands"]["columns"] = 9
        self.assertTrue(compiler.validate_layout_spec(bad))
        bad = copy.deepcopy(self.layout)
        bad["name"] = ""
        self.assertTrue(compiler.validate_layout_spec(bad))

    def test_layout_compile_is_deterministic(self):
        a = compiler.compile_layout(self.layout)
        b = compiler.compile_layout(self.layout)
        self.assertEqual(a, b)
        self.assertEqual(hashlib.sha256(a.encode()).hexdigest(), hashlib.sha256(b.encode()).hexdigest())

    def test_layout_css_budget_and_no_literal_colors(self):
        css = compiler.compile_layout(self.layout)
        self.assertLessEqual(len(css.encode("utf-8")), 8 * 1024)
        self.assertLessEqual(css.count("{"), 120)
        self.assertIsNone(compiler.COLOR_LITERAL.search(css))
        for bad in ("!important", "@import", "url("):
            self.assertNotIn(bad, css)
        self.assertIn('html[data-layout="news-dense"]', css)
        self.assertIn("--layout-band-cols: 4", css)
        self.assertIn("--layout-cover-ratio: 4 / 3", css)

    def test_layout_registry(self):
        reg = compiler.layout_registry(self.layout)
        self.assertEqual(reg["archetype"], "news")
        self.assertFalse(reg["sidebar"])
        self.assertTrue(reg["nav"])
        self.assertTrue(reg["lead"])
        self.assertTrue(reg["bands"])
        self.assertFalse(reg["toc"])
        self.assertEqual(reg["status"], "published")

    def test_theme_rejects_missing_and_extra_token(self):
        bad = copy.deepcopy(self.theme)
        bad["tokens"].pop("--brand")
        self.assertTrue(compiler.validate_theme_spec(bad))
        bad = copy.deepcopy(self.theme)
        bad["tokens"]["--layout-gap"] = "12px"
        self.assertTrue(compiler.validate_theme_spec(bad))
        bad = copy.deepcopy(self.theme)
        bad["tokens"]["--brand"] = "url(https://evil.example/x.png)"
        self.assertTrue(compiler.validate_theme_spec(bad))

    def test_theme_compile_only_root_and_tokens(self):
        self.assertEqual(len(compiler.TOKEN_ORDER), 29)
        css = compiler.compile_theme(self.theme)
        self.assertEqual(theme_lint.lint_theme_css(css), [])
        self.assertEqual(css.count("{"), 1)
        self.assertIn(":root {", css)
        self.assertIn("color-scheme: light;", css)
        for token in compiler.TOKEN_ORDER:
            self.assertIn("%s:" % token, css)
        self.assertEqual(compiler.theme_registry(self.theme)["status"], "published")

    def test_theme_contrast_gate(self):
        bad = copy.deepcopy(self.theme)
        bad["tokens"]["--brand"] = "#eeeeee"
        css = compiler.compile_theme(bad)
        errors = theme_lint.lint_theme_css(css)
        self.assertTrue(any("对比度" in e for e in errors), errors)

    def test_cli_compile_smoke(self):
        tmp = tempfile.mkdtemp(prefix="jiye-compile-")
        try:
            for spec, out in ((LAYOUT, os.path.join(tmp, "layout")), (THEME, os.path.join(tmp, "theme"))):
                r = subprocess.run(
                    [sys.executable, os.path.join(ROOT, "tools/ai-template/cli.py"),
                     "compile", "--spec", spec, "--out", out],
                    cwd=ROOT, capture_output=True, text=True,
                )
                self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
            self.assertTrue(os.path.exists(os.path.join(tmp, "layout", "news-dense.css")))
            self.assertTrue(os.path.exists(os.path.join(tmp, "layout", "news-dense.registry.json")))
            self.assertTrue(os.path.exists(os.path.join(tmp, "theme", "mist.css")))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
