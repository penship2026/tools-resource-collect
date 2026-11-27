#!/usr/bin/env python3
"""A3 预览与闸门测试：静态错误码、预览 HTML、G6、CLI 冒烟。"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "ai-template"))

import cli  # noqa: E402

metrics = cli.preview.metrics
preview = cli.preview
LAYOUT_SPEC = json.loads((ROOT / "tests" / "fixtures" / "specs" / "layout-news-dense.json").read_text(encoding="utf-8"))
THEME_SPEC = json.loads((ROOT / "tests" / "fixtures" / "specs" / "theme-mist.json").read_text(encoding="utf-8"))
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def load_mock(kind):
    from adapters import mock
    return mock.layout_candidates()[0] if kind == "layout" else mock.theme_candidates()[0]


class StaticGateTest(unittest.TestCase):
    def test_layout_static_all_pass(self):
        report = metrics.evaluate_static(LAYOUT_SPEC, "layout")
        self.assertTrue(report["ok"])
        self.assertEqual([g["gate"] for g in report["gates"]], ["G1", "G2", "G5", "G4"])
        self.assertTrue(all(g["ok"] for g in report["gates"]))

    def test_theme_static_all_pass(self):
        report = metrics.evaluate_static(THEME_SPEC, "theme")
        self.assertTrue(report["ok"])
        self.assertTrue(all(g["ok"] for g in report["gates"]))

    def test_schema_error_has_g1_code(self):
        bad = json.loads(json.dumps(LAYOUT_SPEC))
        bad["sidebar"] = "left"
        report = metrics.evaluate_static(bad, "layout")
        self.assertFalse(report["ok"])
        self.assertEqual(report["gates"][0]["code"], "G1_SCHEMA")
        self.assertTrue(report["gates"][0]["errors"])

    def test_layout_g6_structure_requires_two_diffs(self):
        same = json.loads(json.dumps(LAYOUT_SPEC))
        same["bands"]["columns"] = 3
        same["cards"]["coverRatio"] = "16:10"
        same["hero"]["type"] = "lead"
        same["density"] = "comfortable"
        gate = metrics.g6_static(same, "layout")
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["code"], "G6_STRUCTURE")

    def test_theme_g6_against_display(self):
        gate = metrics.g6_static(load_mock("theme"), "theme")
        self.assertTrue(gate["ok"], gate)
        same = json.loads(json.dumps(load_mock("theme")))
        same["tokens"]["--brand"] = "#2d7ff9"
        same["tokens"]["--bg"] = "#f7f8fa"
        same["tokens"]["--radius"] = "14px"
        same["tokens"]["--font-display"] = (
            '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", '
            '"Hiragino Sans GB", "Microsoft YaHei", sans-serif'
        )
        self.assertFalse(metrics.g6_static(same, "theme")["ok"])


class PreviewHtmlTest(unittest.TestCase):
    def test_layout_preview_uses_candidate_without_runtime_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            css = Path(tmp) / "news-dense.css"
            css.write_text("html[data-layout='news-dense']{}", encoding="utf-8")
            html = preview.build_preview(load_mock("layout"), "layout", css, Path(tmp) / "index.html")
            text = html.read_text(encoding="utf-8")
        self.assertIn('data-layout="news-dense"', text)
        self.assertIn("byArchetype[\"news-dense\"]", text)
        self.assertIn(Path(css).resolve().as_uri(), text)
        self.assertNotIn('<script src="assets/layout.js">', text)
        self.assertIn("assets/themes/default.css", text)

    def test_theme_preview_layers_candidate_after_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            css = Path(tmp) / "mist.css"
            css.write_text(":root{--brand:#2f6f4e;}", encoding="utf-8")
            html = preview.build_preview(load_mock("theme"), "theme", css,
                                         Path(tmp) / "index.html", base_theme="dark")
            text = html.read_text(encoding="utf-8")
        self.assertIn('assets/themes/dark.css', text)
        self.assertIn('id="ai-theme"', text)
        self.assertIn(Path(css).resolve().as_uri(), text)
        self.assertGreater(text.index(Path(css).resolve().as_uri()), text.index("assets/themes/dark.css"))

    def test_dom_gate_errors_have_codes(self):
        rows = [{
            "width": 390, "theme": "default", "overflow": 16,
            "cards": 7, "cardsVisible": 7, "cardsTapOk": 0,
            "navs": 2, "navsClickable": 1, "headings": [2, 4],
            "fixed": [], "failedCss": [], "errors": ["console: boom"]
        }]
        gates = preview._dom_gates(rows)
        codes = {g["gate"]: g.get("code") for g in gates}
        self.assertEqual(codes["G3"], "G3_RENDER")
        self.assertEqual(codes["G4"], "G4_DOM")
        self.assertTrue(gates[0]["errors"])

    def test_no_shot_report_marks_visual_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = preview.evaluate(load_mock("layout"), "layout", tmp, no_shot=True)
        self.assertTrue(report["ok"])
        self.assertEqual(report["visual"], "skipped")
        self.assertEqual(report["metrics"]["shots"], 0)

    def test_cli_preview_no_shot(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = Path(tmp) / "spec.json"
            spec.write_text(json.dumps(load_mock("theme"), ensure_ascii=False), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = cli.main(["preview", "--spec", str(spec), "--out", tmp, "--no-shot"])
            self.assertEqual(code, 0)
            self.assertTrue((Path(tmp) / "metrics.json").exists())
        payload = json.loads(out.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["visual"], "skipped")


@unittest.skipUnless(CHROME.exists(), "需要本机 Chrome 跑 G3/G4")
class ChromeSmokeTest(unittest.TestCase):
    def test_theme_quick_shot_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = preview.evaluate(load_mock("theme"), "theme", tmp, quick=True)
        self.assertTrue(report["ok"], report["gates"])
        self.assertEqual(report["metrics"]["shots"], 3)


if __name__ == "__main__":
    unittest.main()
