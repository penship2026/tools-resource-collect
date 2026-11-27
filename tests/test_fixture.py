"""A0 固定 fixture:6 个启用板块 + 1 个空板块,不依赖真实收藏。"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class PreviewFixtureTest(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "tests/fixtures/preview.html"), encoding="utf-8") as fh:
            self.html = fh.read()

    def test_seven_sections_six_enabled_one_empty(self):
        sections = re.findall(r'<section class="section-band" id="sec-(\w+)"', self.html)
        self.assertEqual(len(sections), 7)
        self.assertIn("empty", sections)
        self.assertNotIn("https://", self.html)
        self.assertNotIn("http://", self.html)

    def test_reuses_existing_assets(self):
        for asset in ("assets/style.css", "assets/theme.js", "assets/templates.js", "assets/layout.js"):
            self.assertIn(asset, self.html)

    def test_no_real_personal_data(self):
        for key in ("jiye.mine.v1", "localStorage"):
            self.assertNotIn(key, self.html)


if __name__ == "__main__":
    unittest.main()
