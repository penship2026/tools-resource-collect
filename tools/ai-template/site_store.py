#!/usr/bin/env python3
"""A4 展示清单落盘：只改 site.yml 的 display + assets/site.js，不碰数据与 editorial。"""
from __future__ import annotations

import datetime
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DISPLAY_MAX = 5
LOCKED = {"layout": "standard", "theme": "default"}
DEFAULTS = {
    "layout": ["standard", "news", "magazine"],
    "theme": ["default", "dark", "tech", "campus", "classical"],
}


def _site_file(root):
    return Path(root) / "site.yml"


def _site_js(root):
    return Path(root) / "assets" / "site.js"


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def read_display(root=ROOT):
    path = _site_file(root)
    out = {"visible_layouts": list(DEFAULTS["layout"]),
           "visible_themes": list(DEFAULTS["theme"])}
    if not path.exists():
        return out
    lines = path.read_text(encoding="utf-8").splitlines()
    in_display = False
    current = None
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if _indent(line) == 0:
            in_display = line.strip() == "display:"
            current = None
            continue
        if not in_display:
            continue
        content = line.strip()
        key, _, raw = content.partition(":")
        key = key.strip()
        if key in ("visible_layouts", "visible_themes"):
            current = key
            out[key] = []
            if raw.strip() == "[]":
                current = None
            continue
        if content.startswith("- ") and current:
            value = content[2:].strip().strip("'\"")
            if value:
                out[current].append(value)
        elif _indent(line) <= 2:
            current = None
    if not out["visible_layouts"]:
        out["visible_layouts"] = list(DEFAULTS["layout"])
    if not out["visible_themes"]:
        out["visible_themes"] = list(DEFAULTS["theme"])
    return out


def _display_block(layouts, themes):
    lines = ["display:", "  visible_layouts:"]
    lines.extend("    - %s" % key for key in layouts)
    lines.append("  visible_themes:")
    lines.extend("    - %s" % key for key in themes)
    return lines


def validate_display(kind, keys):
    if not isinstance(keys, list) or not keys:
        raise ValueError("display 不能为空")
    if len(keys) > DISPLAY_MAX:
        raise ValueError("display 最多 %d 套" % DISPLAY_MAX)
    if len(keys) != len(set(keys)):
        raise ValueError("display 含重复 key")
    if LOCKED[kind] not in keys:
        raise ValueError("display 必须包含锁定项 %s" % LOCKED[kind])
    for key in keys:
        if not re.fullmatch(r"[a-z0-9-]{3,24}", str(key)):
            raise ValueError("display 含非法 key:%s" % key)
    return keys


def _replace_display_block(text, layouts, themes):
    lines = text.splitlines()
    start = None
    end = None
    for i, line in enumerate(lines):
        if _indent(line) == 0 and line.strip() == "display:":
            start = i
            end = i + 1
            while end < len(lines):
                if lines[end].strip() and _indent(lines[end]) == 0:
                    break
                end += 1
            break
    block = _display_block(layouts, themes)
    if start is not None:
        lines[start:end] = block + [""]
    else:
        insert_at = None
        for i, line in enumerate(lines):
            if _indent(line) == 0 and line.strip() == "editorial:":
                insert_at = i
                break
        if insert_at is None:
            insert_at = len(lines)
        lines[insert_at:insert_at] = block + [""]
    return "\n".join(lines).rstrip() + "\n"


def _atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(str(tmp), str(path))
    finally:
        if tmp.exists():
            tmp.unlink()


def write_display(visible_layouts, visible_themes, root=ROOT):
    validate_display("layout", list(visible_layouts))
    validate_display("theme", list(visible_themes))
    path = _site_file(root)
    old_yaml = path.read_bytes() if path.exists() else None
    old_js = _site_js(root).read_bytes() if _site_js(root).exists() else None
    try:
        text = path.read_text(encoding="utf-8") if path.exists() else "version: 1\n\nsite:\n  default_layout: standard\n"
        # default_layout 若为 AI key，必须仍在展示清单里；A4 默认保持 standard。
        m = re.search(r"(?m)^  default_layout:\s*([a-z0-9-]+)", text)
        default_layout = m.group(1) if m else "standard"
        if default_layout not in visible_layouts:
            raise ValueError("default_layout %s 必须出现在 visible_layouts" % default_layout)
        _atomic_write(path, _replace_display_block(text, list(visible_layouts), list(visible_themes)))
        _write_site_js(root, {"visible_layouts": list(visible_layouts),
                              "visible_themes": list(visible_themes)})
    except Exception:
        if old_yaml is not None:
            _atomic_write(path, old_yaml.decode("utf-8"))
        elif path.exists():
            path.unlink()
        if old_js is not None:
            _atomic_write(_site_js(root), old_js.decode("utf-8"))
        elif _site_js(root).exists():
            _site_js(root).unlink()
        raise
    return read_display(root)


def _object_after(text, name):
    # 只认行首赋值，避免注释里的 “window.EDITORIAL” 说明文字命中
    matches = re.finditer(r"(?m)^[ \t]*window\.%s\s*=" % re.escape(name), text)
    match = next(matches, None)
    if match is None:
        return None
    brace = text.find("{", match.end())
    if brace < 0:
        return None
    depth = 0
    quote = None
    escape = False
    for i in range(brace, len(text)):
        ch = text[i]
        if quote:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[brace:i + 1]
    return None


def _write_site_js(root, display):
    path = _site_js(root)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    raw = _object_after(existing, "SITE_CONFIG")
    config = {}
    if raw:
        try:
            config = json.loads(raw)
        except ValueError:
            config = {}
    config.setdefault("default_layout", "standard")
    config["display"] = display
    editorial = {}
    raw_ed = _object_after(existing, "EDITORIAL")
    if raw_ed:
        try:
            editorial = json.loads(raw_ed)
        except ValueError:
            editorial = {}
    lines = [
        "// 站点外观与编辑推荐,由 generate.py 从 site.yml 生成",
        "// 页面用 window.SITE_CONFIG / window.EDITORIAL 读取;修改请改 site.yml",
        "window.SITE_CONFIG = %s;" % json.dumps(config, ensure_ascii=False),
        "window.EDITORIAL = %s;" % json.dumps(editorial, ensure_ascii=False, indent=2),
        'window.SITE_CONFIG_UPDATED = %s;' % json.dumps(datetime.date.today().isoformat()),
    ]
    _atomic_write(path, "\n".join(lines) + "\n")
