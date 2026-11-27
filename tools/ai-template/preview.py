#!/usr/bin/env python3
"""A3 预览与闸门：固定 fixture + 候选 CSS → 三档截图 + G1–G6。

G3/G4/G6 依赖本机 Chrome/CDP；`--no-shot` 只跑静态部分并标记视觉未验证。
版式：5 套展示主题 × 1280/768/390；主题：同一 fixture 套 5 套展示主题 × 三档。
"""
from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

import metrics  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "preview.html"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SIZES = metrics.SIZES
THEMES = metrics.DISPLAY_THEMES

ERROR_HOOK = """
window.__previewErrors = [];
window.addEventListener('error', function (e) {
  window.__previewErrors.push('error: ' + (e.message || 'resource'));
});
window.addEventListener('unhandledrejection', function (e) {
  window.__previewErrors.push('rejection: ' + (e.reason && e.reason.message || e.reason));
});
var __origConsoleError = console.error;
console.error = function () {
  try { window.__previewErrors.push('console: ' + Array.prototype.join.call(arguments, ' ')); } catch (e) {}
  return __origConsoleError.apply(console, arguments);
};
"""

DOM_JS = """(() => {
  const visible = el => {
    const s = getComputedStyle(el), r = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0;
  };
  const rect = el => { const r = el.getBoundingClientRect(); return {w: r.width, h: r.height, x: r.x, y: r.y}; };
  const cards = Array.from(document.querySelectorAll('.topic-card'));
  const navs = Array.from(document.querySelectorAll('.header-nav a, .section-link'));
  const headings = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6')).map(h => Number(h.tagName[1]));
  const fixed = Array.from(document.querySelectorAll('*')).filter(el => getComputedStyle(el).position === 'fixed').map(el => {
    const r = el.getBoundingClientRect();
    return {cls: el.className || el.tagName, w: r.width, h: r.height, x: r.x, y: r.y, area: r.width * r.height};
  });
  const failedCss = Array.from(document.querySelectorAll('link[rel="stylesheet"]')).filter(l => !l.sheet).map(l => l.getAttribute('href'));
  return {
    overflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - document.documentElement.clientWidth,
    cards: cards.length,
    cardsVisible: cards.filter(visible).length,
    cardsTapOk: cards.filter(el => visible(el) && rect(el).w >= 44 && rect(el).h >= 44).length,
    navs: navs.filter(visible).length,
    navsClickable: navs.filter(el => visible(el) && getComputedStyle(el).pointerEvents !== 'none').length,
    headings: headings,
    fixed: fixed,
    failedCss: failedCss,
    layout: document.documentElement.getAttribute('data-layout'),
    theme: document.documentElement.getAttribute('data-theme')
  };
})()"""

FOCUS_JS = """(() => {
  const a = document.activeElement;
  if (!a) return {tag: '', outline: 'none'};
  const s = getComputedStyle(a);
  return {tag: a.tagName, cls: a.className, outline: s.outlineStyle,
          outlineWidth: s.outlineWidth, boxShadow: s.boxShadow};
})()"""


def _shot_module():
    name = "jiye_shot_matrix"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / "shot_matrix.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_fixture():
    return FIXTURE.read_text(encoding="utf-8")


def build_preview(spec, kind, css_path, out_html, base_theme="default"):
    """把固定 fixture 改成候选预览；只写候选目录，不碰 assets/。"""
    html = _load_fixture()
    html = html.replace('<base href="../../">', '<base href="%s/">' % ROOT.as_uri())
    css_uri = Path(css_path).resolve().as_uri()
    if kind == "layout":
        key = spec["key"]
        archetype = spec["archetype"]
        html = html.replace('<script src="assets/layout.js"></script>', "")
        html = html.replace(
            '<html lang="zh-CN">',
            '<html lang="zh-CN" data-layout="%s">' % key,
        )
        html = html.replace(
            '<script src="assets/templates.js"></script>',
            '<script src="assets/templates.js"></script>\n'
            '  <script>(function(){var c=window.TEMPLATE_CAPABILITIES;'
            'c.byArchetype["%s"]=Object.assign({},c.byArchetype["%s"]);})();</script>' % (key, archetype),
        )
        theme_link = '<link rel="stylesheet" id="theme-css" href="assets/themes/default.css">'
        themed_link = theme_link.replace("default.css", "%s.css" % base_theme)
        html = html.replace(
            theme_link,
            themed_link + '\n  <link rel="stylesheet" id="layout-css" href="%s">' % css_uri,
        )
        # 让内置主题保持可切换，但不要让 layout.js 再覆盖候选
        html = html.replace(
            '</head>',
            '<script>document.documentElement.setAttribute("data-layout", "%s");</script>\n</head>' % key,
        )
    else:
        key = spec["key"]
        base_link = '<link rel="stylesheet" id="theme-css" href="assets/themes/default.css">'
        themed_link = base_link.replace("default.css", "%s.css" % base_theme)
        html = html.replace(
            base_link,
            themed_link + '\n  <link rel="stylesheet" id="ai-theme" href="%s">' % css_uri,
        )
        html = html.replace('<html lang="zh-CN">', '<html lang="zh-CN" data-theme="%s">' % key)
    out_html = Path(out_html)
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(html, encoding="utf-8")
    return out_html


def _preview_url(html_path, theme=None, layout=None):
    params = []
    if layout:
        params.append("layout=" + layout)
    if theme:
        params.append("theme=" + theme)
    return Path(html_path).resolve().as_uri() + ("?" + "&".join(params) if params else "")


def _fail(name, code, message, **details):
    return {"gate": name, "ok": False, "code": code, "message": message, **details}


def _pass(name, message="", **details):
    return {"gate": name, "ok": True, "code": None, "message": message, **details}


def _dom_gates(rows):
    if not rows:
        return [_fail("G3", "G3_SHOT_UNAVAILABLE", "未运行 Chrome/CDP 截图")]
    g3 = []
    g4 = []
    g5 = []
    for row in rows:
        key = "%d@%s" % (row["width"], row.get("theme") or "-")
        if row["overflow"] > 0:
            g3.append("%s 横向溢出 %dpx" % (key, row["overflow"]))
        if row["cardsVisible"] < 6:
            g3.append("%s 可见卡片仅 %d/%d" % (key, row["cardsVisible"], row["cards"]))
        if row["navs"] and row["navsClickable"] < row["navs"]:
            g3.append("%s 导航不可点 %d/%d" % (key, row["navsClickable"], row["navs"]))
        if row["errors"]:
            g3.append("%s 控制台错误 %d 条" % (key, len(row["errors"])))
        if row["failedCss"]:
            g3.append("%s 样式加载失败 %s" % (key, row["failedCss"]))
        if row["cardsTapOk"] < row["cardsVisible"]:
            g4.append("%s 卡片点击区不足 44px %d/%d" % (key, row["cardsTapOk"], row["cardsVisible"]))
        levels = row["headings"]
        for i in range(1, len(levels)):
            if levels[i] - levels[i - 1] > 1:
                g4.append("%s 标题层级跳跃 h%d → h%d" % (key, levels[i - 1], levels[i]))
                break
        for item in row["fixed"]:
            if item["area"] > 0.25 * row["width"] * row["height"]:
                g5.append("%s 固定定位遮挡过大 %s" % (key, item["cls"]))
    return [
        _fail("G3", "G3_RENDER", "渲染断言失败", errors=g3) if g3 else _pass("G3", "三档渲染通过", shots=len(rows)),
        _fail("G4", "G4_DOM", "无障碍 DOM 断言失败", errors=g4) if g4 else _pass("G4", "点击区/标题层级通过"),
        _fail("G5", "G5_FIXED", "固定定位遮挡", errors=g5) if g5 else _pass("G5", "无固定定位遮挡"),
    ]


def _focus_gate(cdp):
    try:
        cdp.call("Input.dispatchKeyEvent", {
            "type": "keyDown", "key": "Tab", "code": "Tab",
            "windowsVirtualKeyCode": 9, "nativeVirtualKeyCode": 9,
        })
        cdp.call("Input.dispatchKeyEvent", {
            "type": "keyUp", "key": "Tab", "code": "Tab",
            "windowsVirtualKeyCode": 9, "nativeVirtualKeyCode": 9,
        })
        focus = cdp.eval(FOCUS_JS) or {}
    except Exception as exc:
        return _fail("G4", "G4_FOCUS_UNVERIFIED", "焦点检测失败:%s" % exc)
    style = (focus.get("outline") or "none").lower()
    shadow = focus.get("boxShadow") or "none"
    if style == "none" and shadow == "none":
        return _fail("G4", "G4_FOCUS", "键盘焦点不可见", focus=focus)
    return _pass("G4", "键盘焦点可见", focus=focus)


def _take_shots(html_path, kind, limit_themes=None):
    sm = _shot_module()
    if not Path(CHROME).exists():
        raise RuntimeError("找不到 Chrome:%s" % CHROME)
    cdp = sm.CDP()
    cdp.call("Page.enable", {})
    cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": ERROR_HOOK})
    rows = []
    try:
        for theme in (limit_themes or THEMES):
            base_layout = "news" if kind == "theme" else None
            url = _preview_url(html_path, theme=theme, layout=base_layout)
            for width, height in SIZES:
                shot = None
                for attempt in range(2):
                    try:
                        shot = cdp.shot(url, width, height)
                        dom = cdp.eval(DOM_JS) or {}
                        errors = cdp.eval("window.__previewErrors || []") or []
                        break
                    except Exception:
                        if attempt == 0:
                            time.sleep(0.8)
                            continue
                        raise
                rows.append({
                    "width": width, "height": height,
                    "theme": theme,
                    "overflow": max(int(shot.get("overflow_x") or 0), int(dom.get("overflow") or 0)),
                    "cards": int(dom.get("cards") or 0),
                    "cardsVisible": int(dom.get("cardsVisible") or 0),
                    "cardsTapOk": int(dom.get("cardsTapOk") or 0),
                    "navs": int(dom.get("navs") or 0),
                    "navsClickable": int(dom.get("navsClickable") or 0),
                    "headings": dom.get("headings") or [],
                    "fixed": dom.get("fixed") or [],
                    "failedCss": dom.get("failedCss") or [],
                    "errors": errors,
                    "dhash": shot.get("dhash"),
                    "layout": dom.get("layout") or shot.get("layout"),
                })
        focus = _focus_gate(cdp)
    finally:
        cdp.close()
    return rows, focus


def _base_layout_shot(archetype, out_dir):
    sm = _shot_module()
    cdp = sm.CDP()
    try:
        cdp.call("Page.enable", {})
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": ERROR_HOOK})
        html = build_preview(
            {"key": archetype, "archetype": archetype}, "layout",
            metrics.LAYOUT_DIR / ("%s.css" % archetype),
            Path(out_dir) / ("base-%s.html" % archetype), base_theme="default",
        )
        shot = cdp.shot(_preview_url(html, theme="default"), 1280, 900)
        return shot.get("dhash")
    finally:
        cdp.close()


def evaluate(spec, kind, out_dir, no_shot=False, quick=False):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = {"version": 1, "kind": kind, "key": spec.get("key"), "created_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00")}
    static = metrics.evaluate_static(spec, kind)
    gates = list(static.get("gates", []))
    report["gates"] = gates
    report["metrics"] = {"cssBytes": static.get("bytes", 0), "rules": static.get("rules", 0)}
    if not static.get("ok"):
        report["ok"] = False
        report["visual"] = "not-run"
        return report

    css_path = out / ("%s.css" % spec["key"])
    if not css_path.exists():
        css_path.write_text(static["css"], encoding="utf-8")
    html = build_preview(spec, kind, css_path, out / "preview" / "index.html")
    report["preview"] = str(html.relative_to(out))

    if no_shot:
        report["visual"] = "skipped"
        report["shots"] = []
        report["metrics"]["shots"] = 0
        if kind == "layout":
            gates.append(metrics.g6_static(spec, kind))
        else:
            gates.append(metrics.g6_static(spec, kind))
        report["g6"] = gates[-1]
        report["ok"] = all(g.get("ok") for g in gates)
        return report

    try:
        rows, focus = _take_shots(html, kind, limit_themes=("default",) if quick else None)
    except Exception as exc:
        gates.append(_fail("G3", "G3_SHOT_UNAVAILABLE", "截图不可用:%s" % exc))
        gates.append(_fail("G4", "G4_UNVERIFIED", "截图不可用，无障碍未验证"))
        gates.append(_fail("G6", "G6_UNVERIFIED", "截图不可用，辨识度未验证"))
        report["visual"] = "unavailable"
        report["shots"] = []
        report["ok"] = False
        return report
    report["shots"] = rows
    report["visual"] = "checked"
    report["metrics"]["shots"] = len(rows)
    gates.extend(_dom_gates(rows))
    gates.append(focus)
    gates.append(metrics.g6_static(spec, kind))
    if kind == "layout":
        try:
            base_dhash = _base_layout_shot(spec["archetype"], out)
            shot_default = next((r for r in rows if r["width"] == 1280 and r["theme"] == "default"), rows[0])
            diff = sum(1 for a, b in zip(shot_default.get("dhash", ""), base_dhash or "") if a != b)
            if diff < 10:
                gates.append(_fail("G6", "G6_DHASH", "与基座版式截图 dHash 差 %d < 10" % diff, diff=diff))
            else:
                gates.append(_pass("G6", "与基座版式截图 dHash 差 %d" % diff, diff=diff))
        except Exception as exc:
            gates.append(_fail("G6", "G6_DHASH_UNVERIFIED", "dHash 对比失败:%s" % exc))
    report["ok"] = all(g.get("ok") for g in gates)
    report["g6"] = [g for g in gates if g["gate"] == "G6"]
    return report
