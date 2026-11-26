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
                     'id="toggle-topics"', "function toggleAreaCards", "function cardsFor"):
            self.assertIn(text, html)
        self.assertIn('data-area-head="section"', html)
        self.assertIn('data-area-head="topic"', html)
        self.assertIn("function toggleArea", html)
        self.assertNotIn('id="toggle-all"', html)


if __name__ == "__main__":
    unittest.main()
