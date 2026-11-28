import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "ai-template"))

import studio  # noqa: E402
from adapters.openai_compat import OpenAICompat  # noqa: E402


class FakeAdapter(OpenAICompat):
    model = "fake-studio"
    base_url = "http://fake"

    def __init__(self):
        self.result = {}

    def complete(self, system, user, kind=None):
        return json.dumps(self.result, ensure_ascii=False)


def fixture_theme(root):
    src = Path(__file__).resolve().parents[1] / "tools" / "ai-template" / "builtin-specs" / "theme" / "default.json"
    return json.loads(src.read_text(encoding="utf-8"))


class PageEditorTest(unittest.TestCase):
    def _root(self, tmp):
        root = Path(tmp)
        (root / "assets/data").mkdir(parents=True)
        (root / "assets/data/index.js").write_text(
            'window.COLLECTION_INDEX = [{"id": "topic-test"}];\n', encoding="utf-8")
        (root / "assets/pages").mkdir(parents=True)
        (root / "index.html").write_text(self._page("home"), encoding="utf-8")
        (root / "assets/pages/index.css").write_text("body{}", encoding="utf-8")
        return root

    @staticmethod
    def _page(text):
        return ('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
                '<link rel="stylesheet" href="assets/pages/index.css"></head>'
                '<body><main>%s</main></body></html>' % text)

    def test_page_catalog_preview_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            data = studio.page_catalog(root)
            self.assertEqual(len(data["items"]), 4)
            self.assertEqual(data["items"][0]["preview"], "/repo/index.html")
            self.assertIn("?id=topic-test", data["items"][1]["preview"])
            self.assertEqual(data["items"][3]["preview"], "/repo/single.html?id=topic-test")

    def test_page_save_backs_up_and_rejects_outside(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            studio.save_page(root, "index.html", self._page("v2"))
            self.assertIn("v2", (root / "index.html").read_text(encoding="utf-8"))
            self.assertTrue(list((root / "backups/pages").glob("*/*")))
            with self.assertRaises(studio.StudioError):
                studio.save_page(root, "../index.html", "<html></html>")

    def test_page_history_keeps_latest_twenty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            for n in range(2, 25):
                studio.save_page(root, "index.html", self._page("v%d" % n))
            data = studio.list_page_history(root, "index.html")
            self.assertTrue(data["ok"])
            self.assertEqual(data["items"][0]["version"], "current")
            self.assertEqual(len(data["items"]), 21)
            self.assertEqual(data["history_count"], 20)
            self.assertEqual(data["max"], 20)
            latest = studio.read_page_history(root, "index.html", data["items"][1]["version"])
            self.assertIn("v23", latest["content"])
            current = studio.read_page_history(root, "index.html", "current")
            self.assertIn("v24", current["content"])
            self.assertEqual(len(list((root / "backups/pages").glob("*"))), 20)

    def test_page_history_rejects_bad_version_and_outside_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            studio.save_page(root, "index.html", self._page("v2"))
            with self.assertRaises(studio.StudioError):
                studio.read_page_history(root, "index.html", "../x")
            with self.assertRaises(studio.StudioError):
                studio.list_page_history(root, "../index.html")

    def test_page_edit_fake_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            fake = FakeAdapter()
            fake.complete = lambda system, user, kind=None: "<html><body>edited</body></html>"
            out = studio.edit_page(root, "index.html", "<html><body>home</body></html>", "把正文改成 edited", adapter=fake)
            self.assertEqual(out["content"], "<html><body>edited</body></html>")
            fake.complete = lambda system, user, kind=None: "<html><body>broken"
            with self.assertRaises(studio.StudioError):
                studio.edit_page(root, "index.html", "<html><body>home</body></html>", "改坏", adapter=fake)

    def test_page_validate_blocks_bad_html_and_css(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            good = self._page("ok")
            report = studio.validate_page(root, "index.html", good)
            self.assertTrue(report["ok"], report["errors"])
            with self.assertRaises(studio.StudioError) as ctx:
                studio.save_page(root, "index.html", "<html><body>broken</body></html>")
            self.assertEqual(ctx.exception.code, "PAGE_VALIDATE")
            self.assertIn("DOCTYPE", " ".join(x["message"] for x in ctx.exception.details["errors"]))
            self.assertNotIn("broken", (root / "index.html").read_text(encoding="utf-8"))
            missing = studio.validate_page(
                root, "index.html", good.replace("assets/pages/index.css", "assets/pages/none.css"))
            self.assertFalse(missing["ok"])
            self.assertTrue(any(x["code"] == "PAGE_HTML_CSS" for x in missing["errors"]))
            css_bad = studio.validate_page(root, "assets/pages/index.css", "body{color:red;")
            self.assertFalse(css_bad["ok"])
            self.assertTrue(any(x["code"] == "PAGE_CSS_BRACE" for x in css_bad["errors"]))
            css_html = studio.validate_page(root, "assets/pages/index.css", "body{}</style><script>")
            self.assertFalse(css_html["ok"])
            self.assertTrue(any(x["code"] == "PAGE_CSS_HTML" for x in css_html["errors"]))

    def test_page_history_diff_with_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            studio.save_page(root, "index.html", self._page("v2"))
            old = studio.list_page_history(root, "index.html")["items"][1]["version"]
            diff = studio.diff_page_history(root, "index.html", old, "current")
            self.assertTrue(diff["ok"])
            self.assertEqual(diff["left"]["version"], old)
            self.assertEqual(diff["right"]["version"], "current")
            self.assertEqual(diff["stats"], {"added": 1, "removed": 1})
            with self.assertRaises(studio.StudioError):
                studio.diff_page_history(root, "index.html", old, old)


class DesignHistoryTest(unittest.TestCase):
    def _root(self, tmp):
        key = Path(tmp) / "tools/ai-template/drafts/news-x"
        for name, title in (("candidate-1", "A"), ("candidate-2", "B"), ("studio-preview", "draft")):
            folder = key / name
            folder.mkdir(parents=True)
            (folder / "spec.json").write_text(
                json.dumps({"kind": "layout", "key": "news-x", "name": title}),
                encoding="utf-8",
            )
        return Path(tmp), "tools/ai-template/drafts/news-x/candidate-2/spec.json"

    def test_design_history_lists_current_and_skips_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, path = self._root(tmp)
            data = studio.list_design_history(root, path)
            self.assertEqual(data["type"], "design")
            self.assertEqual(data["current"]["version"], "candidate-2")
            self.assertEqual([x["version"] for x in data["items"]], ["candidate-2", "candidate-1"])
            self.assertNotIn("studio-preview", [x["version"] for x in data["items"]])
            item = studio.read_design_history(root, path, "candidate-1")
            self.assertEqual(item["version"], "candidate-1")
            self.assertEqual(item["basePath"], path)
            self.assertEqual(item["path"], "tools/ai-template/drafts/news-x/candidate-1/spec.json")
            diff = studio.diff_design_history(root, path, "candidate-1", "current")
            self.assertEqual(diff["stats"], {"added": 1, "removed": 1})
            with self.assertRaises(studio.StudioError):
                studio.read_design_history(root, path, "../spec.json")


class StudioEditTest(unittest.TestCase):
    def test_theme_edit_keeps_identity(self):
        spec = fixture_theme(None)
        new = dict(spec)
        new["name"] = "更深青绿"
        new["tokens"]["--brand"] = "#1B4D3E"
        fake = FakeAdapter()
        fake.result = new
        result = studio.edit_spec(spec, "theme", "只把品牌色改成更深的青绿", adapter=fake)
        self.assertEqual(result["spec"]["key"], spec["key"])
        self.assertEqual(result["spec"]["tokens"]["--brand"], "#1B4D3E")

    def test_rejects_changed_key(self):
        spec = fixture_theme(None)
        new = dict(spec, key="other")
        fake = FakeAdapter()
        fake.result = new
        with self.assertRaises(studio.StudioError):
            studio.edit_spec(spec, "theme", "改 key", adapter=fake)

    def test_preview_draft_writes_readonly_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = fixture_theme(None)
            out = studio.preview_draft(spec, "theme", root=root)
            self.assertEqual(out["candidate"], "studio-preview")
            self.assertTrue((root / "tools/ai-template/drafts/default/studio-preview/spec.json").exists())
            self.assertTrue((root / "tools/ai-template/drafts/default/studio-preview/default.css").exists())



if __name__ == "__main__":
    unittest.main()
