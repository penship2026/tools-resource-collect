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
        self.assertIn('id="toggle-all"', html)
        self.assertIn("settings-guide.html", html)
        self.assertIn('class="section-card is-collapsed"', html)
        self.assertIn('class="topic-row is-collapsed"', html)

    def test_guide_covers_key_fields(self):
        guide = (ROOT / "collector" / "settings-guide.html").read_text(encoding="utf-8")
        for text in ("must", "any", "作者锁", "立即执行", "数据同步 Git"):
            self.assertIn(text, guide)


if __name__ == "__main__":
    unittest.main()
