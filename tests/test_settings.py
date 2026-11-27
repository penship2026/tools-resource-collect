"""设置页配置与 Pages 隔离的离线回归。"""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "collector"))

import generate  # noqa: E402
import git_sync  # noqa: E402
import settings_store  # noqa: E402


class SettingsStoreTest(unittest.TestCase):
    def test_reserved_sections_cannot_be_removed(self):
        sections = generate.load_sections_yaml()
        with self.assertRaises(ValueError):
            settings_store.normalize_sections([s for s in sections if s["id"] != "k12"])

    def test_keyword_counts_are_enforced(self):
        sections = generate.load_sections_yaml()
        with self.assertRaises(ValueError):
            settings_store.normalize_topics([{
                "id": "bad", "section": "tools", "title": "坏主题",
                "must_keywords": ["a", "b", "c", "d", "e"],
                "channels": ["bilibili"],
            }], sections)

    def test_dump_round_trip(self):
        sections = generate.load_sections_yaml()
        topics = generate.load_topics_yaml(generate.TOPICS_FILE)
        tmp = tempfile.mkdtemp(prefix="jiye-settings-")
        sp = os.path.join(tmp, "sections.yml")
        tp = os.path.join(tmp, "topics.yml")
        with open(sp, "w", encoding="utf-8") as fh:
            fh.write(settings_store.dump_sections(sections))
        with open(tp, "w", encoding="utf-8") as fh:
            fh.write(settings_store.dump_topics(topics))
        got_sections = generate.load_sections_yaml(sp)
        got_topics = generate.load_topics_yaml(tp, sections_path=sp)
        self.assertEqual(len(got_sections), 7)
        self.assertEqual(len(got_topics), 7)
        self.assertEqual(got_topics[0]["must_keywords"], topics[0]["must_keywords"])

    def test_merge_section_preserves_reserved_age(self):
        sections = generate.load_sections_yaml()
        merged, _ = settings_store.merge_section(sections, "infant-care", {
            "title": "婴幼儿照护", "description": "0–3 岁照护",
        })
        item = next(s for s in merged if s["id"] == "infant-care")
        self.assertEqual(item["title"], "婴幼儿照护")
        self.assertEqual((item["age_min_months"], item["age_max_months"]), (0, 36))
        self.assertEqual(len(merged), 7)

    def test_merge_topic_updates_fields_without_losing_section(self):
        sections = generate.load_sections_yaml()
        topics = generate.load_topics_yaml(generate.TOPICS_FILE)
        merged = settings_store.merge_topic(topics, "daily-website", {
            "title": "每天一个网站",
            "any_keywords": ["网站", "工具"],
            "channels": ["bilibili", "wechat"],
        })
        item = next(t for t in merged if t["id"] == "daily-website")
        self.assertEqual(item["section"], "tools")
        self.assertEqual(item["title"], "每天一个网站")
        self.assertEqual(item["any_keywords"], ["网站", "工具"])
        self.assertEqual(item["channels"], ["bilibili", "wechat"])

    def test_merge_can_create_section_and_topic(self):
        sections = generate.load_sections_yaml()
        created_sections, _ = settings_store.merge_section(sections, "coding", {
            "title": "编程启蒙", "description": "全龄编程与计算思维",
            "order": 8, "enabled": True,
        })
        self.assertEqual(len(created_sections), 8)
        item = next(s for s in created_sections if s["id"] == "coding")
        self.assertEqual(item["title"], "编程启蒙")
        self.assertIsNone(item["age_min_months"])

        topics = generate.load_topics_yaml(generate.TOPICS_FILE)
        created_topics = settings_store.merge_topic(topics, "coding-kids", {
            "section": "coding", "title": "少儿编程",
            "must_keywords": ["少儿编程"], "any_keywords": [],
            "channels": ["bilibili", "xhs"], "enabled": True,
        })
        topic = next(t for t in created_topics if t["id"] == "coding-kids")
        self.assertEqual(topic["section"], "coding")
        self.assertEqual(topic["channels"], ["bilibili", "xhs"])

    def test_git_path_whitelist(self):
        self.assertTrue(git_sync._allowed("assets/data/index.js"))
        self.assertTrue(git_sync._allowed("assets/data/collections/daily-website.js"))
        self.assertFalse(git_sync._allowed("collector/server.py"))
        self.assertFalse(git_sync._allowed("docs/PLAN.md"))


class PagesArtifactTest(unittest.TestCase):
    def test_pages_workflow_excludes_collector(self):
        path = os.path.join(ROOT, ".github", "workflows", "pages.yml")
        text = open(path, encoding="utf-8").read()
        self.assertIn("upload-pages-artifact", text)
        self.assertIn("rm -rf _site/collector", text)
        self.assertIn("_site/topics.yml", text)
        self.assertIn("cp -R assets/. _site/assets/", text)
        self.assertIn("mine-io.html", text)


if __name__ == "__main__":
    unittest.main()
