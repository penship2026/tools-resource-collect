"""解析器离线回归(D14):不联网,只用 fixtures 里的真实页面结构片段。
运行: python3 -m unittest discover -s tests
"""
import os
import sys
import unittest

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
