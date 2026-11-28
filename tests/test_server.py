#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设置页局域网 Origin 白名单测试。"""

import os
import pathlib
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "collector"))
import server  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]


class OriginTest(unittest.TestCase):
    def test_mine_io_is_public_static_page(self):
        """个人站导入导出页必须进本地静态白名单,否则会返回「未对外开放的路径」."""
        self.assertIn("/mine-io.html", server.Handler.STATIC_EXACT)

    def test_local_hosts_allowed(self):
        for host in ("127.0.0.1", "localhost", "::1"):
            self.assertTrue(server.origin_host_allowed(host))

    def test_private_lan_hosts_allowed(self):
        for host in ("192.168.1.23", "10.0.0.8", "172.20.10.2", "macbook.local"):
            self.assertTrue(server.origin_host_allowed(host))

    def test_public_or_empty_hosts_rejected(self):
        for host in ("", "evil.com", "8.8.8.8", "172.32.0.1"):
            self.assertFalse(server.origin_host_allowed(host))

    def test_lan_ip_shape(self):
        value = server.lan_ip()
        self.assertIsInstance(value, str)


class CollectOnlyAssetsTest(unittest.TestCase):
    def test_collect_theme_assets_are_allowed(self):
        """采集端专用模式必须放行主题脚本与主题 CSS,否则页面会丢 token 样式。"""
        for path in ("/assets/style.css", "/assets/theme.js",
                     "/assets/themes/default.css", "/assets/themes/dark.css?x=1"):
            self.assertTrue(server.collect_asset_allowed(path), path)

    def test_collect_only_does_not_open_other_assets(self):
        for path in ("/assets/data/index.js", "/assets/site.js", "/assets/templates.js"):
            self.assertFalse(server.collect_asset_allowed(path), path)

    def test_collect_page_uses_root_asset_urls(self):
        """/collect.html 与 /collector/collect.html 两种入口都能解析到同一份主题资源。"""
        html = (ROOT / "collector" / "collect.html").read_text(encoding="utf-8")
        for path in ('href="/assets/style.css"', 'src="/assets/theme.js"',
                     'href="/assets/themes/default.css"'):
            self.assertIn(path, html)


class SettingsPageTest(unittest.TestCase):
    def test_default_collapsed_and_guide_link(self):
        html = (ROOT / "collector" / "settings.html").read_text(encoding="utf-8")
        self.assertIn("settings-guide.html", html)
        self.assertIn("section-card is-collapsed", html)
        self.assertIn("topic-row is-collapsed", html)

    def test_guide_covers_key_fields(self):
        guide = (ROOT / "collector" / "settings-guide.html").read_text(encoding="utf-8")
        for text in ("must", "any", "作者锁", "立即执行", "数据同步 Git"):
            self.assertIn(text, guide)

    def test_channel_picker_and_section_sorting(self):
        html = (ROOT / "collector" / "settings.html").read_text(encoding="utf-8")
        self.assertIn('class="channel-picker"', html)
        self.assertIn('data-f="channels" value=', html)
        self.assertIn("var sortSections = function", html)
        self.assertIn("state.sections = sortSections(state.sections)", html)

    def test_area_search_and_independent_toggles(self):
        html = (ROOT / "collector" / "settings.html").read_text(encoding="utf-8")
        for text in ('id="search-sections"', 'id="search-topics"', 'id="toggle-sections"',
                     'id="toggle-topics"', "function toggleAreaCards", "function allItemsOpen"):
            self.assertIn(text, html)
        self.assertIn('data-area-head="section"', html)
        self.assertIn('data-area-head="topic"', html)
        self.assertIn("function toggleArea", html)
        self.assertNotIn('id="toggle-all"', html)

    def test_section_pagination(self):
        html = (ROOT / "collector" / "settings.html").read_text(encoding="utf-8")
        for text in ('id="section-pagination"', "var PAGE_SIZE = 10", "var renderSectionPagination",
                     "shown.slice(", 'data-page-dir="prev"', 'data-page-dir="next"'):
            self.assertIn(text, html)

    def test_add_forms_replace_browser_prompts(self):
        html = (ROOT / "collector" / "settings.html").read_text(encoding="utf-8")
        for text in ('id="form-modal"', 'id="add-section-id"', 'id="add-topic-id"',
                     "function openAddForm", "function readSectionForm", "function readTopicForm"):
            self.assertIn(text, html)
        self.assertNotIn("window.prompt", html)
        self.assertNotIn("alert(", html)

    def test_add_buttons_in_sticky_area_header(self):
        html = (ROOT / "collector" / "settings.html").read_text(encoding="utf-8")
        self.assertIn("position: sticky", html)
        for area in ("section", "topic"):
            head = html.index('data-area-head="%s"' % area)
            add = html.index('id="add-%s"' % area)
            body = html.index('data-area-body="%s"' % area)
            self.assertLess(head, add)
            self.assertLess(add, body)


if __name__ == "__main__":
    unittest.main()
