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
        (root / "index.html").write_text("<html><body>home</body></html>", encoding="utf-8")
        (root / "assets/pages/index.css").write_text("body{}", encoding="utf-8")
        return root

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
            studio.save_page(root, "index.html", "<html><body>v2</body></html>")
            self.assertIn("v2", (root / "index.html").read_text(encoding="utf-8"))
            self.assertTrue(list((root / "backups/pages").glob("*/*")))
            with self.assertRaises(studio.StudioError):
                studio.save_page(root, "../index.html", "<html></html>")

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
