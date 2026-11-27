"""A0 契约骨架:版式/主题 schema、能力矩阵与 29 token 白名单。不依赖第三方 JSON Schema。"""
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
        return json.load(fh)


class SpecSchemaTest(unittest.TestCase):
    def setUp(self):
        self.layout = load("spec/layout.schema.json")
        self.theme = load("spec/theme.schema.json")

    def test_layout_contract(self):
        props = self.layout["properties"]
        self.assertEqual(props["kind"], {"const": "layout"})
        self.assertFalse(self.layout["additionalProperties"])
        for required in ("nav", "hero", "bands", "cards", "responsive", "limits", "rationale"):
            self.assertIn(required, self.layout["required"])
        self.assertEqual(props["archetype"]["enum"], ["standard", "news", "magazine"])
        # 未落地能力不进 schema
        self.assertNotIn("sidebar", props)
        self.assertNotIn("rails", props)
        self.assertNotIn("timeline", props)
        self.assertNotIn("theme", props)

    def test_theme_tokens_exact(self):
        tokens = self.theme["properties"]["tokens"]
        required = tokens["required"]
        self.assertEqual(len(required), 29)
        self.assertEqual(set(required), set(tokens["properties"].keys()))
        self.assertFalse(tokens["additionalProperties"])
        self.assertFalse(any(k.startswith("--layout-") for k in required))
        self.assertNotIn("sidebar", self.theme["properties"])
        self.assertNotIn("archetype", self.theme["properties"])

    def test_theme_tokens_match_default_css(self):
        with open(os.path.join(ROOT, "assets/themes/default.css"), encoding="utf-8") as fh:
            css = fh.read()
        names = set(re.findall(r"(--[a-z0-9-]+)\s*:", css))
        spec = set(self.theme["properties"]["tokens"]["required"])
        self.assertEqual(names, spec)

    def test_capability_matrix_shared(self):
        with open(os.path.join(ROOT, "assets/templates.js"), encoding="utf-8") as fh:
            js = fh.read()
        self.assertIn("window.TEMPLATE_CAPABILITIES", js)
        for key in ("nav", "lead", "bands", "toc", "sidebar", "rail", "timeline"):
            self.assertIn(key, js)
        self.assertIn("byArchetype", js)


if __name__ == "__main__":
    unittest.main()
