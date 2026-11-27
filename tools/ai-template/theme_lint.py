#!/usr/bin/env python3
"""主题 CSS lint：只允许 :root + 29 token，检查禁用项与对比度。"""
from __future__ import annotations

import re

from compiler import TOKEN_ORDER

COMMENT = re.compile(r"/\*.*?\*/", re.S)
ROOT_BLOCK = re.compile(r"^\s*:root\s*\{([^}]*)\}\s*$", re.S)
COLOR = re.compile(r"#[0-9a-fA-F]{3,8}|rgba?\([^)]*\)|hsla?\([^)]*\)")


def _rgb(value):
    value = value.strip()
    m = re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", value)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    m = re.fullmatch(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*[\d.]+)?\s*\)", value)
    if m:
        return tuple(int(m.group(i)) for i in (1, 2, 3))
    return None


def _lum(rgb):
    def channel(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a, b):
    ra, rb = _rgb(a), _rgb(b)
    if ra is None or rb is None:
        return None
    la, lb = _lum(ra), _lum(rb)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def lint_theme_css(css):
    errors = []
    clean = COMMENT.sub("", css).strip()
    m = ROOT_BLOCK.fullmatch(clean)
    if not m:
        return ["主题 CSS 只能包含一个 :root 块，不能有选择器/页面覆盖"]
    body = m.group(1)
    for bad in ("url(", "@import", "!important"):
        if bad in clean:
            errors.append("出现禁用内容 %s" % bad)
    decls = {}
    for item in body.split(";"):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            errors.append("非法声明:%s" % item)
            continue
        key, value = item.split(":", 1)
        key, value = key.strip(), value.strip()
        if key in decls:
            errors.append("重复声明:%s" % key)
        decls[key] = value
    for key in decls:
        if key == "color-scheme":
            continue
        if key.startswith("--layout-"):
            errors.append("主题不能声明布局变量:%s" % key)
        elif key not in TOKEN_ORDER:
            errors.append("未知 token:%s" % key)
    for token in TOKEN_ORDER:
        if token not in decls:
            errors.append("缺少 token:%s" % token)
    if decls.get("color-scheme") not in ("light", "dark"):
        errors.append("color-scheme 必须是 light / dark")
    checks = [
        ("--text", "--bg", 4.5),
        ("--text-sub", "--surface", 4.5),
        ("--brand", "--bg", 3.0),
    ]
    for fg, bg, minimum in checks:
        if fg not in decls or bg not in decls:
            continue
        ratio = contrast(decls[fg], decls[bg])
        if ratio is None:
            errors.append("%s / %s 不是可解析的实色，无法检查对比度" % (fg, bg))
        elif ratio < minimum:
            errors.append("%s / %s 对比度 %.2f < %.1f" % (fg, bg, ratio, minimum))
    return errors


def lint_theme_file(path):
    with open(path, encoding="utf-8") as fh:
        return lint_theme_css(fh.read())
