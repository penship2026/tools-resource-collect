"""解析器离线回归(D14):不联网,只用 fixtures 里的真实页面结构片段。
运行: python3 -m unittest discover -s tests
"""
import os
import sys
import unittest
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "collector"))
import platforms  # noqa: E402

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


class SearchParserTest(unittest.TestCase):
    def test_baidu_mobile_keeps_wechat_only(self):
        pairs = platforms._parse_search_page("wechat", "baidu_mobile", fixture("baidu_mobile.html"))
        self.assertEqual(len(pairs), 1)
        self.assertIn("mp.weixin.qq.com", pairs[0]["url"])
        # 标题里的站点后缀被清掉
        self.assertEqual(pairs[0]["title"], "一篇公众号文章")

    def test_so360_keeps_note_only(self):
        pairs = platforms._parse_search_page("xhs", "so360", fixture("so360.html"))
        self.assertEqual(len(pairs), 1)
        # xsec_token 等查询参数被剥离
        self.assertEqual(pairs[0]["url"],
                         "https://www.xiaohongshu.com/explore/65f0a1b2c3d4e5f6a7b8c9d0")
        self.assertEqual(pairs[0]["title"], "一篇小红书笔记标题")

    def test_dedupe_same_url(self):
        page = fixture("baidu_mobile.html")
        page += page  # 同一页重复出现
        pairs = platforms._parse_search_page("wechat", "baidu_mobile", page)
        self.assertEqual(len(pairs), 1)


class XhsStateTest(unittest.TestCase):
    def test_extract_note(self):
        state = platforms._xhs_state(fixture("xhs_state.html"))
        self.assertIsNotNone(state)
        note = platforms._xhs_find_note(state)
        self.assertEqual(note["noteId"], "65f0a1b2")
        self.assertEqual(note["title"], "测试笔记")
        self.assertEqual(platforms._xhs_cover(note), "https://sns-img.example.com/x.jpg")


class SearchTopicAccountTest(unittest.TestCase):
    """账号限定:公众号把账号名拼进检索式;小红书没有账号维度,传入即忽略。"""

    def _run_search(self, platform_key, account):
        calls = []
        real_get = platforms._get
        real_parse = platforms._parse_search_page

        def fake_get(url, headers=None, timeout=None):
            calls.append(url)
            return "", "<html></html>"

        def fake_parse(key, parser, page):
            return [{"url": "https://mp.weixin.qq.com/s/abc", "title": "每日一站 第1期"}]

        try:
            platforms._get = fake_get
            platforms._parse_search_page = fake_parse
            hits = platforms.search_topic("每日一站", platform_key, limit=20,
                                          log=lambda *a: None, account=account)
        finally:
            platforms._get = real_get
            platforms._parse_search_page = real_parse
        return hits, calls

    def test_wechat_account_goes_into_query(self):
        hits, calls = self._run_search("wechat", "草根的异世界")
        self.assertEqual(len(hits), 1)
        self.assertTrue(calls)
        self.assertIn(urllib.parse.quote("草根的异世界"), calls[0])
        self.assertIn(urllib.parse.quote("每日一站"), calls[0])

    def test_xhs_account_is_ignored(self):
        hits, calls = self._run_search("xhs", "某个账号")
        self.assertEqual(len(hits), 1)
        self.assertTrue(calls)
        self.assertNotIn(urllib.parse.quote("某个账号"), calls[0])


class UrlHelpersTest(unittest.TestCase):
    def test_detect_platform(self):
        self.assertEqual(platforms.detect_platform("https://www.bilibili.com/video/BV1xx"), "bilibili")
        self.assertEqual(platforms.detect_platform("https://mp.weixin.qq.com/s/abc"), "wechat")
        self.assertEqual(platforms.detect_platform("https://www.xiaohongshu.com/explore/abc"), "xhs")

    def test_extract_urls_from_share_text(self):
        text = "看看这个 https://www.bilibili.com/video/BV1ab411c7de?p=1 很有意思"
        urls = platforms.extract_urls(text)
        self.assertIn("https://www.bilibili.com/video/BV1ab411c7de?p=1", urls)


if __name__ == "__main__":
    unittest.main()
