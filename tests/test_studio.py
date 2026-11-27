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
