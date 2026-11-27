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

    def test_public_pages_have_skip_link_and_main_anchor(self):
        for page in ["index.html", "series.html", "list.html", "single.html"]:
            html = read(page)
            self.assertIn('class="skip-link" href="#main-content"', html, page)
            self.assertIn('id="main-content"', html, page)

    def test_subpages_render_section_breadcrumb(self):
        for page in ["series.html", "list.html", "single.html"]:
            html = read(page)
            self.assertIn("assets/data/sections.js", html, page)
            self.assertIn("Render.breadcrumb(Render.sectionMeta(topic)", html, page)
            self.assertNotIn('id="crumb-title"', html, page)
        self.assertIn("'全部内容'", read("list.html"))

    def test_index_heading_outline(self):
        html = read("index.html")
        self.assertIn('<h1 class="sr-only">集页</h1>', html)
        self.assertIn('<h2 id="hero-title">', html)
        self.assertNotIn('<h1 id="hero-title">', html)

    def test_mine_actions_use_independent_footer(self):
        idx = read("index.html")
        self.assertNotIn('id="mine-export"', idx)
        self.assertNotIn('id="mine-import"', idx)
        self.assertNotIn('name="mine-mode"', idx)
        self.assertIn('id="public-footer"', idx)
        self.assertIn('id="mine-footer"', idx)
        mine_footer = idx[idx.index('id="mine-footer"'):idx.index('</footer>', idx.index('id="mine-footer"'))]
        self.assertIn('mine-io.html', mine_footer)
        self.assertIn('id="mine-settings"', mine_footer)
        self.assertNotIn('采集入口', mine_footer)
        self.assertTrue(os.path.exists(os.path.join(ROOT, "mine-io.html")))
        io = read("mine-io.html")
        self.assertIn('name="io-mode"', io)
        self.assertIn('id="io-export"', io)
        self.assertIn('id="io-import"', io)
        self.assertIn('assets/personal.js', io)

    def test_mine_footer_has_no_theme_or_layout_switch(self):
        for asset in ("assets/theme.js", "assets/layout.js"):
            self.assertIn(":not(.mine-footer)", read(asset), asset)

    def test_mine_view_keeps_section_navigation(self):
        js = read("assets/personal.js")
        self.assertIn("mineSection", js)
        self.assertIn("mineScoped", js)
        self.assertIn("unitSection", js)
        idx = read("index.html")
        self.assertIn("mineView ? { view: 'mine' } : null", idx)

    def test_detail_pages_keep_mine_view(self):
        """从我的收藏进入详情后,面包屑与返回链接必须回到我的页。"""
        for page in ("series.html", "single.html", "list.html"):
            html = read(page)
            self.assertIn("view === 'mine'", html, page)
            self.assertIn("id=\"brand-link\"", html, page)
            self.assertIn("id=\"back-link\"", html, page)
            self.assertIn("返回我的收藏", html, page)
            self.assertIn("{ view: view }", html, page)
        js = read("assets/personal.js")
        self.assertIn("series.html?id=' + encodeURIComponent(it.unit) + '&view=mine'", js)
        self.assertIn("single.html?id=' + encodeURIComponent(it.unit) + '&k=' + encodeURIComponent(it.key) + '&view=mine'", js)

    def test_mine_cards_reuse_public_topic_card(self):
        js = read("assets/personal.js")
        self.assertIn("Render.topicCard", js)
        self.assertIn("topic-grid", js)
        self.assertNotIn("fav-card", js)
        self.assertNotIn("fav-del", js)

    def test_nav_items_min_touch_height(self):
        css = read("assets/pages/index.css")
        block = re.search(r"\.section-tab \{([^}]*)\}", css)
        self.assertIsNotNone(block)
        self.assertIn("min-height: 44px", block.group(1))

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
        self.assertIn("filterMine", js)
        self.assertIn("mine-filter-bar", js)
        self.assertIn("seriesButton", js)
        self.assertIn("__series", js)
        self.assertIn("mineSubtitle", js)

    def test_mine_settings_hooks(self):
        """我的页设置:标题 + 我的页专属主题,且主题键与公开主题分离"""
        idx = read(os.path.join(ROOT, "index.html"))
        for hook in ('id="mine-settings"', 'id="mine-settings-panel"', 'id="mine-set-title"', 'id="mine-set-sub"',
                     'id="mine-set-public"', 'id="mine-set-switch"', 'id="mine-set-theme"', 'id="mine-set-save"', 'id="mine-sub"',
                     'id="mine-filter-bar"', 'id="mine-tag-chips"', 'id="mine-search"',
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

    def test_layout_registry_and_loader(self):
        """D65/D68:注册表 3 套、默认 standard;版式只接公开页,采集工具页不接"""
        js = read("assets/templates.js")
        for key in ("standard", "news", "magazine"):
            self.assertIn(key + ":", js)
        self.assertIn("default: 'standard'", js)
        self.assertTrue(os.path.exists(os.path.join(ROOT, "assets/layouts/standard.css")))
        loader = read("assets/layout.js")
        for token in ("jiye.layout", "layout=", "data-layout", "data-layout-fallback", "jiye:layout"):
            self.assertIn(token, loader)
        for page in ("index.html", "series.html", "list.html", "single.html"):
            html = read(page)
            self.assertIn("assets/templates.js", html, page)
            self.assertIn("assets/layout.js", html, page)
            self.assertLess(html.index("assets/templates.js"), html.index("assets/layout.js"), page)
        for tool in ("collector/collect.html", "collector/settings.html"):
            self.assertNotIn("assets/layout.js", read(tool), tool)

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

    def test_layout_unit_tests(self):
        if not NODE:
            self.skipTest("未安装 node")
        r = subprocess.run([NODE, os.path.join(ROOT, "tests", "test_layout.js")],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout[-800:] + r.stderr[-800:])
        self.assertIn("全部通过", r.stdout)

    def test_render_unit_tests(self):
        if not NODE:
            self.skipTest("未安装 node")
        r = subprocess.run([NODE, os.path.join(ROOT, "tests", "test_render.js")],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout[-800:] + r.stderr[-800:])
        self.assertIn("全部通过", r.stdout)


if __name__ == "__main__":
    unittest.main()
