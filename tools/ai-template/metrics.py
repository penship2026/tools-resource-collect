#!/usr/bin/env python3
"""A3 指标与静态闸门：G1 Schema、G2 编译、G4 token 对比度、G5 预算、G6 辨识度。"""
from __future__ import annotations

import json
import re
from pathlib import Path

import compiler
import theme_lint

ROOT = Path(__file__).resolve().parents[2]
THEME_DIR = ROOT / "assets" / "themes"
LAYOUT_DIR = ROOT / "assets" / "layouts"

DISPLAY_LAYOUTS = ("standard", "news", "magazine")
DISPLAY_THEMES = ("default", "dark", "tech", "campus", "classical")
SIZES = ((1280, 900), (768, 900), (390, 844))

# 内置版式的结构指纹；候选必须与基座至少差 2 项。
BASE_LAYOUT_SIGNATURES = {
    "standard": (3, "16:9", "text", "comfortable"),
    "news": (3, "16:10", "lead", "comfortable"),
    "magazine": (3, "3:2", "text", "comfortable"),
}

HEX = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})")
RGBA = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")
DECL = re.compile(r"--([a-z0-9-]+)\s*:\s*([^;]+);")


def gate(name, code=None, message="", **details):
    return {"gate": name, "ok": code is None, "code": code, "message": message, **details}


def css_bytes(css):
    return len(css.encode("utf-8"))


def css_rules(css):
    return css.count("{")


def color_rgb(value):
    if not isinstance(value, str):
        return None
    m = HEX.search(value)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    m = RGBA.search(value)
    if m:
        return tuple(int(m.group(i)) for i in (1, 2, 3))
    return None


def luminance(value):
    rgb = color_rgb(value)
    if rgb is None:
        return None
    def channel(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def rgb_distance(a, b):
    ra, rb = color_rgb(a), color_rgb(b)
    if ra is None or rb is None:
        return 0
    return sum((x - y) ** 2 for x, y in zip(ra, rb)) ** 0.5


def parse_tokens(css):
    tokens = {}
    body = css
    if ":root" in body:
        body = body.split(":root", 1)[1]
        if "{" in body:
            body = body.split("{", 1)[1].split("}", 1)[0]
    for name, value in DECL.findall(body):
        tokens["--" + name] = value.strip()
    return tokens


def read_tokens(key, base_dir=THEME_DIR):
    path = Path(base_dir) / ("%s.css" % key)
    if not path.exists():
        return {}
    return parse_tokens(path.read_text(encoding="utf-8"))


def display_theme_tokens():
    return {key: read_tokens(key) for key in DISPLAY_THEMES}


def contrast_errors(tokens, include_brand=True):
    errors = []
    pairs = [
        ("--text", "--bg", 4.5),
        ("--text-sub", "--surface", 4.5),
    ]
    if include_brand:
        pairs.append(("--brand", "--bg", 3.0))
    for fg, bg, minimum in pairs:
        ratio = theme_lint.contrast(tokens.get(fg, ""), tokens.get(bg, ""))
        if ratio is None:
            errors.append("%s/%s 颜色无法计算" % (fg, bg))
        elif ratio < minimum:
            errors.append("%s/%s %.2f < %.1f" % (fg, bg, ratio, minimum))
    return errors


def layout_signature(spec):
    return (
        int(spec["bands"]["columns"]),
        spec["cards"]["coverRatio"],
        spec["hero"]["type"],
        spec["density"],
    )


def signature_diff(a, b):
    labels = ("列数", "封面比例", "首屏类型", "密度")
    diffs = [label for label, x, y in zip(labels, a, b) if x != y]
    return len(diffs), diffs


def px_value(value):
    m = re.match(r"\s*(-?\d+(?:\.\d+)?)px", value or "")
    return float(m.group(1)) if m else None


def theme_diff(candidate, base):
    """主色、背景、字体、圆角四项里明显不同的项数。"""
    diffs = []
    if rgb_distance(candidate.get("--brand"), base.get("--brand")) >= 50:
        diffs.append("主色")
    ca, cb = luminance(candidate.get("--bg")), luminance(base.get("--bg"))
    if ca is not None and cb is not None and abs(ca - cb) >= 0.03:
        diffs.append("背景")
    if candidate.get("--font-display") != base.get("--font-display"):
        diffs.append("字体")
    ra, rb = px_value(candidate.get("--radius")), px_value(base.get("--radius"))
    if ra is not None and rb is not None and abs(ra - rb) >= 2:
        diffs.append("圆角")
    return diffs


def evaluate_static(spec, kind):
    """G1 + G2 + G5 + token 部分的 G4/G6；不依赖 Chrome。"""
    gates = []
    if kind not in ("layout", "theme"):
        return {"ok": False, "kind": kind, "css": "", "gates": [gate("G1", "G1_KIND", "kind 必须是 layout/theme")]}
    if kind == "layout":
        errors = compiler.validate_layout_spec(spec)
    else:
        errors = compiler.validate_theme_spec(spec)
    if errors:
        gates.append(gate("G1", "G1_SCHEMA", "Spec 不符合契约", errors=errors))
        return {"ok": False, "kind": kind, "css": "", "gates": gates}
    gates.append(gate("G1", message="schema 通过"))

    try:
        result = compiler.compile_spec(spec, kind=kind, no_timestamp=True)
    except compiler.SpecError as exc:
        gates.append(gate("G2", "G2_COMPILE", "编译失败", errors=exc.errors))
        return {"ok": False, "kind": kind, "css": "", "gates": gates}
    css = result["css"]
    size = css_bytes(css)
    rules = css_rules(css)

    problems = []
    for bad in ("!important", "@import", "url("):
        if bad in css:
            problems.append("出现禁用内容 %s" % bad)
    if kind == "layout":
        if compiler.COLOR_LITERAL.search(css):
            problems.append("版式 CSS 出现直接颜色")
        if size > 10 * 1024:
            problems.append("版式 CSS %d bytes > 10KB" % size)
        if rules > 160:
            problems.append("版式 CSS %d 规则 > 160" % rules)
        else:
            lint = []
    else:
        lint = theme_lint.lint_theme_css(css)
        problems.extend(lint)
        if size > 4 * 1024:
            problems.append("主题 CSS %d bytes > 4KB" % size)
        if re.search(r"@font-face|https?://", css):
            problems.append("主题 CSS 含外链字体/URL")
    if problems:
        gates.append(gate("G2", "G2_FORBIDDEN" if any("禁用" in p or "直接颜色" in p for p in problems)
                          else "G2_BUDGET", "编译产物不合格", errors=problems))
    else:
        gates.append(gate("G2", message="编译与 CSS 白名单通过", bytes=size, rules=rules))

    perf = []
    if kind == "layout" and size > 8 * 1024:
        perf.append("版式 CSS %d bytes > 8KB" % size)
    if kind == "theme" and size > 4 * 1024:
        perf.append("主题 CSS %d bytes > 4KB" % size)
    if re.search(r"url\(|@import|@font-face|https?://", css):
        perf.append("CSS 含外部资源/字体")
    if perf:
        gates.append(gate("G5", "G5_BUDGET", "超出性能预算", errors=perf))
    else:
        gates.append(gate("G5", message="无外部资源，体积在预算内", bytes=size))

    if kind == "theme":
        errors = contrast_errors(spec.get("tokens", {}))
        if errors:
            gates.append(gate("G4", "G4_CONTRAST", "主题 token 对比度不足", errors=errors))
        else:
            gates.append(gate("G4", message="主题 token 对比度通过"))
    else:
        errors = []
        for key, tokens in display_theme_tokens().items():
            for err in contrast_errors(tokens, include_brand=False):
                errors.append("%s: %s" % (key, err))
        if errors:
            gates.append(gate("G4", "G4_CONTRAST", "展示主题对比度不足", errors=errors))
        else:
            gates.append(gate("G4", message="5 套展示主题 token 对比度通过"))

    return {"ok": True, "kind": kind, "css": css, "bytes": size, "rules": rules,
            "gates": gates, "registry": result.get("registry")}


def g6_static(spec, kind):
    if kind == "layout":
        sig = layout_signature(spec)
        base = BASE_LAYOUT_SIGNATURES.get(spec.get("archetype"))
        if not base:
            return gate("G6", "G6_STRUCTURE", "未知 archetype，无法对比结构")
        diff, labels = signature_diff(sig, base)
        if diff < 2:
            return gate("G6", "G6_STRUCTURE", "与基座版式结构差异不足 2 项",
                        diff=diff, labels=labels)
        return gate("G6", message="结构差异 %d 项" % diff, diff=diff, labels=labels,
                    signature=sig, base=base)
    tokens = spec.get("tokens", {})
    baselines = display_theme_tokens()
    bad = []
    for key, base in baselines.items():
        diffs = theme_diff(tokens, base)
        if len(diffs) < 2:
            bad.append("%s 仅差 %s" % (key, "/".join(diffs) or "0 项"))
    if bad:
        return gate("G6", "G6_TOKEN", "与当前展示主题辨识度不足", errors=bad)
    return gate("G6", message="与 5 套展示主题均至少差 2 项")


def write_report(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
