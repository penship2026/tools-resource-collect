"""页面结构回归:视图层收口后的契约检查(D21/D14)。只读静态文件,不联网。
运行: python3 -m unittest discover -s tests
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ["index.html", "series.html", "list.html", "single.html", "collector/collect.html"]
THEMED = ["index.html", "series.html", "list.html", "single.html", "collector/collect.html"]
NODE = shutil.which("node")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


class PagesContractTest(unittest.TestCase):
    def test_render_js_exists(self):
        self.assertTrue(os.path.exists(os.path.join(ROOT, "assets/render.js")))

    def test_pages_load_render_js_before_inline(self):
        for page in ["index.html", "series.html", "list.html", "single.html"]:
            html = read(page)
            self.assertIn("assets/render.js", html, page)
            pos_render = html.index("assets/render.js")
            pos_inline = html.rindex("<script>")
            self.assertLess(pos_render, pos_inline, "%s: render.js 必须在页面脚本之前加载" % page)

    def test_pages_use_render_functions(self):
        self.assertIn("Render.topicCard", read("index.html"))
        self.assertIn("Render.videoCard", read("series.html"))
        self.assertIn("Render.videoCard", read("list.html"))
        self.assertIn("Render.detail", read("single.html"))
        self.assertIn("Render.episodes", read("single.html"))

    def test_no_duplicate_card_implementation(self):
        """卡片实现只允许存在于 assets/render.js。"""
        for page in PAGES:
            html = read(page)
            self.assertNotIn("class=\"topic-card\" href=", html, page)
            self.assertNotIn("<div class=\"video-thumb\">", html, page)

    def test_mine_title_hooks(self):
        """我的视图:标题可自定义(本机存储),且页面只渲染收藏"""
        idx = read(os.path.join(ROOT, "index.html"))
        for hook in ('id="mine-title"', 'id="mine-title-edit"', 'id="mine-title-input"'):
            self.assertIn(hook, idx)
        js = read(os.path.join(ROOT, "assets/personal.js"))
        self.assertIn("jiye.mine.title.v1", js)
        self.assertIn("mineTitle", js)
        self.assertIn("jiye.mine.subtitle.v1", js)
        self.assertIn("jiye.mine.switch.v1", js)
        self.assertIn("switchLabel", js)
        self.assertIn("jiye.mine.public.v1", js)
        self.assertIn("publicLabel", js)
        self.assertIn("mineSubtitle", js)

    def test_mine_settings_hooks(self):
        """我的页设置:标题 + 我的页专属主题,且主题键与公开主题分离"""
        idx = read(os.path.join(ROOT, "index.html"))
        for hook in ('id="mine-settings"', 'id="mine-settings-panel"', 'id="mine-set-title"', 'id="mine-set-sub"',
                     'id="mine-set-public"', 'id="mine-set-switch"', 'id="mine-set-theme"', 'id="mine-set-save"', 'id="mine-sub"',
                     'class="mine-hero"'):
            self.assertIn(hook, idx)
        js = read(os.path.join(ROOT, "assets/personal.js"))
        self.assertIn("mineChoice", js)
        theme_js = read(os.path.join(ROOT, "assets/theme.js"))
        self.assertIn("jiye.mine.theme.v1", theme_js)
        self.assertIn("setMineChoice", theme_js)
        # 我的页主题只在 ?view=mine 生效,不得覆盖公开主题键
        self.assertIn("view') === 'mine'", theme_js.replace('"', "'"))

    def test_all_theme_files_registered(self):
        """D40:themes/ 下每个 css 都要在 theme.js 的 THEMES 里注册,避免加了文件却切不到"""
        base = os.path.join(ROOT, "assets/themes")
        files = sorted(f for f in os.listdir(base) if f.endswith(".css"))
        self.assertGreaterEqual(len(files), 6, files)
        js = read(os.path.join(ROOT, "assets/theme.js"))
        for name in files:
            self.assertIn(name, js, "theme.js 未注册 %s" % name)

    def test_theme_loaded_in_every_page(self):
        for page in THEMED:
            self.assertIn("theme.js", read(page), page)

    def test_inline_scripts_syntax(self):
        if not NODE:
            self.skipTest("未安装 node")
        for page in PAGES:
            html = read(page)
            blocks = [m.group(2) for m in re.finditer(r"<script([^>]*)>(.*?)</script>", html, re.S)
                      if "src=" not in m.group(1)]
            for block in blocks:
                with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
                    fh.write(block)
                    path = fh.name
                try:
                    r = subprocess.run([NODE, "--check", path], capture_output=True, text=True)
                finally:
                    os.unlink(path)
                self.assertEqual(r.returncode, 0, "%s 内联脚本语法错误: %s" % (page, r.stderr[-400:]))

    def test_render_unit_tests(self):
        if not NODE:
            self.skipTest("未安装 node")
        r = subprocess.run([NODE, os.path.join(ROOT, "tests", "test_render.js")],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout[-800:] + r.stderr[-800:])
        self.assertIn("全部通过", r.stdout)


if __name__ == "__main__":
    unittest.main()
