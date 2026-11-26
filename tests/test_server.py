#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设置页局域网 Origin 白名单测试。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "collector"))
import server  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
