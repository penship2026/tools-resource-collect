#!/usr/bin/env python3
"""版式层自检(M1b 半成品,后续 M5 扩展为截图矩阵前置检查)。

检查项:
  1. 4 个公开页不得再有 <style> 内联块(样式统一在 style.css / pages/*.css)
  2. 页面按顺序引用 style.css → 自己的 pages/*.css
  3. style.css 定义 17 个 --layout-* 默认值
  4. pages/*.css 不写死渠道品牌色(公众号绿 / 小红书红 / 旧渐变蓝)
  5. 页面内联事件里不出现 style= 硬编码颜色;页级 CSS 只允许 token 与中性色 #fff/#000
  6. 版式注册表与 CSS 文件一一对应;site.js / site.yml 存在
  7. 页面脚本顺序 site.js → templates.js → layout.js
退出码:0 通过,1 有问题。
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = {
    "index.html": "assets/pages/index.css",
    "series.html": "assets/pages/series.css",
    "list.html": "assets/pages/list.css",
    "single.html": "assets/pages/single.css",
}
TOKENS = [
    "--layout-wrap", "--layout-gutter", "--layout-header-h", "--layout-hero-pad",
    "--layout-facts-gap", "--layout-section-gap", "--layout-grid-min", "--layout-grid-gap",
    "--layout-card-pad", "--layout-cover-ratio", "--layout-band-cols", "--layout-lead-cols",
    "--layout-side-w", "--layout-detail-cols", "--layout-article-max", "--layout-search-w",
    "--layout-xhs-cols",
]
BANNED_COLORS = ["#07c160", "#ff2442", "#e9f8f0", "#fff0f3", "#1e3a5f", "#2d7ff9"]

problems = []


def read(rel):
    return open(os.path.join(ROOT, rel), encoding="utf-8").read()


def check_pages():
    for page, page_css in PAGES.items():
        html = read(page)
        if "<style>" in html:
            problems.append("%s 仍有 <style> 内联块" % page)
        if 'href="assets/style.css"' not in html:
            problems.append("%s 未引用 style.css" % page)
        if page_css:
            if 'href="%s"' % page_css not in html:
                problems.append("%s 未引用 %s" % (page, page_css))
            order_ok = html.index('href="assets/style.css"') < html.index('href="%s"' % page_css)
            if not order_ok:
                problems.append("%s 样式顺序应为 style.css → %s" % (page, page_css))
        # 内联 style 属性里不应出现颜色/字号,避免再次形成页面级覆盖
        for m in re.finditer(r'style="([^"]*)"', html):
            body = m.group(1)
            if re.search(r"#[0-9a-fA-F]{3,8}|rgba?\(|font-size", body):
                problems.append("%s 的 style 属性含颜色/字号: %s" % (page, body[:60]))


def check_tokens():
    css = read("assets/style.css")
    for token in TOKENS:
        if not re.search(r"%s:\s*[^;]+;" % re.escape(token), css):
            problems.append("style.css 缺少 token: %s" % token)


def check_layout_layer():
    for rel in ("assets/templates.js", "assets/layout.js", "assets/layouts/standard.css"):
        if not os.path.exists(os.path.join(ROOT, rel)):
            problems.append("缺少版式层文件: %s" % rel)
    for page in PAGES:
        html = read(page)
        if "assets/layout.js" not in html:
            problems.append("%s 未接入 layout.js" % page)
        if "assets/templates.js" not in html:
            problems.append("%s 未接入 templates.js" % page)
        if "assets/templates.js" in html and "assets/layout.js" in html:
            if html.index("assets/templates.js") > html.index("assets/layout.js"):
                problems.append("%s: templates.js 必须早于 layout.js" % page)
    for tool in ("collector/collect.html", "collector/settings.html"):
        if "assets/layout.js" in read(tool):
            problems.append("%s 是采集工具页,不应接入版式层" % tool)
    layout_dir = os.path.join(ROOT, "assets/layouts")
    for name in sorted(os.listdir(layout_dir)):
        if not name.endswith(".css"):
            continue
        css = open(os.path.join(layout_dir, name), encoding="utf-8").read()
        for bad in ("!important", "@import", "url("):
            if bad in css:
                problems.append("layouts/%s 含禁用写法: %s" % (name, bad))


def check_registry():
    reg = read("assets/templates.js")
    if "window.TEMPLATES" not in reg:
        problems.append("assets/templates.js 缺少 window.TEMPLATES")
    keys = re.findall(r"^\s{4}([a-z]+):\s*\{", reg, re.M)
    if not keys:
        problems.append("版式注册表没有条目")
    for key in keys:
        block = re.search(r"^\s{4}%s:\s*\{(.*?)^\s{4}\}" % re.escape(key), reg, re.S | re.M)
        if not block:
            problems.append("版式 %s 的注册块无法解析" % key)
            continue
        body = block.group(1)
        m = re.search(r"file:\s*'([^']+)'", body)
        if not m:
            problems.append("版式 %s 缺少 file" % key)
            continue
        rel = m.group(1)
        if not os.path.exists(os.path.join(ROOT, rel)):
            problems.append("版式 %s 的 CSS 不存在: %s" % (key, rel))
        if not re.search(r"label:\s*'[^']+'", body):
            problems.append("版式 %s 缺少中文 label" % key)
        for cap in ("nav", "lead", "bands", "sidebar", "toc"):
            if not re.search(r"%s:\s*(true|false)" % cap, body):
                problems.append("版式 %s 缺少能力声明 %s" % (key, cap))
    if not os.path.exists(os.path.join(ROOT, "site.yml")):
        problems.append("缺少 site.yml")
    if not os.path.exists(os.path.join(ROOT, "assets/site.js")):
        problems.append("缺少 assets/site.js")


def check_script_order():
    for page in PAGES:
        html = read(page)
        marks = ["assets/site.js", "assets/templates.js", "assets/layout.js"]
        pos = [html.find('src="%s"' % m) for m in marks]
        if any(p < 0 for p in pos):
            problems.append("%s 未完整接入 site/templates/layout 三个脚本" % page)
        elif pos != sorted(pos):
            problems.append("%s 脚本顺序应为 site.js → templates.js → layout.js" % page)
    html = read("index.html")
    if 'src="assets/data/sections.js"' not in html:
        problems.append("index.html 未加载 assets/data/sections.js")


def check_page_css():
    for rel in [v for v in PAGES.values() if v]:
        css = read(rel)
        for color in BANNED_COLORS:
            if color in css.lower():
                problems.append("%s 写死了渠道/旧品牌色: %s" % (rel, color))
        if re.search(r"--brand:\s*#", css):
            problems.append("%s 的 --brand 覆盖必须是 var(),不能写死颜色" % rel)
        for m in re.finditer(r"#[0-9a-fA-F]{3,8}\b", css):
            if m.group(0).lower() not in ("#fff", "#ffffff", "#000", "#000000"):
                problems.append("%s 出现 token 之外的硬编码颜色: %s" % (rel, m.group(0)))


def main():
    check_pages()
    check_tokens()
    check_layout_layer()
    check_registry()
    check_script_order()
    check_page_css()
    if problems:
        for p in problems:
            print("✗", p)
        print("版式自检失败: %d 项" % len(problems))
        return 1
    print("版式自检通过:%d 页无内联样式、脚本顺序正确、注册表与 CSS 对齐、17 个 token 齐全、页级样式无渠道色" % len(PAGES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
