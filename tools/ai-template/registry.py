#!/usr/bin/env python3
"""A4 已发布设计库：内置 + AI 发布 sidecar；运行时注册表仍以 assets/*.js 为准。"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUBLISHED_FILE = "tools/ai-template/published.json"
DISPLAY_MAX = 5
LAYOUT_LOCK = "standard"
THEME_LOCK = "default"
LAYOUT_MARKER = "/* AI_LAYOUTS */"
THEME_MARKER = "/* AI_THEMES */"

BUILTIN_LAYOUTS = {
    "standard": {"label": "简洁", "desc": "单列 Hero + 卡片网格(现行)",
                 "file": "assets/layouts/standard.css", "source": "builtin", "status": "published"},
    "news": {"label": "门户", "desc": "板块导航 + 头条区 + 板块分节",
             "file": "assets/layouts/news.css", "source": "builtin", "status": "published"},
    "magazine": {"label": "画册", "desc": "单栏宽幅 + 章节编号 + 目录",
                 "file": "assets/layouts/magazine.css", "source": "builtin", "status": "published"},
}
BUILTIN_THEMES = {
    "default": {"label": "浅色", "file": "default.css", "source": "builtin", "status": "published"},
    "dark": {"label": "深色", "file": "dark.css", "source": "builtin", "status": "published"},
    "tech": {"label": "科技", "file": "tech.css", "source": "builtin", "status": "published"},
    "campus": {"label": "学院", "file": "campus.css", "source": "builtin", "status": "published"},
    "classical": {"label": "古典", "file": "classical.css", "source": "builtin", "status": "published"},
    "anime": {"label": "二次元", "file": "anime.css", "source": "builtin", "status": "published"},
}


def published_path(root=ROOT):
    return Path(root) / PUBLISHED_FILE


def load_published(root=ROOT):
    path = published_path(root)
    if not path.exists():
        return {"layouts": {}, "themes": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        data = {}
    data.setdefault("layouts", {})
    data.setdefault("themes", {})
    data.setdefault("archived", {})
    return data


def dump_published(data, root=ROOT):
    path = published_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def items(kind, root=ROOT):
    data = load_published(root)
    archived = set(data.get("archived", {}).get(kind, []))
    base = BUILTIN_LAYOUTS if kind == "layout" else BUILTIN_THEMES
    out = {}
    for key, item in base.items():
        out[key] = dict(item, key=key, kind=kind, locked=key == (LAYOUT_LOCK if kind == "layout" else THEME_LOCK))
    for key, item in data.get("layouts" if kind == "layout" else "themes", {}).items():
        out[key] = dict(item, key=key, kind=kind,
                        locked=key == (LAYOUT_LOCK if kind == "layout" else THEME_LOCK))
    for key in list(out):
        out[key]["archived"] = key in archived
        out[key]["clonable"] = _has_spec(kind, key, root)
        if key in archived:
            out[key]["status"] = "archived"
    return out


def _has_spec(kind, key, root=ROOT):
    docs = Path(root) / "docs" / "templates" / ("%s.json" % key)
    builtin = Path(root) / "tools" / "ai-template" / "builtin-specs" / kind / ("%s.json" % key)
    return docs.exists() or builtin.exists()


def archive(kind, key, root=ROOT):
    """把旧模板标为归档；不改 CSS、注册表或原 published 条目。"""
    if kind not in ("layout", "theme"):
        raise ValueError("kind 必须是 layout/theme")
    if key not in items(kind, root):
        raise ValueError("设计不存在:%s" % key)
    if key == (LAYOUT_LOCK if kind == "layout" else THEME_LOCK):
        raise ValueError("锁定项不能归档")
    data = load_published(root)
    bucket = data.setdefault("archived", {}).setdefault(kind, [])
    if key not in bucket:
        bucket.append(key)
    dump_published(data, root)
    return {"ok": True, "kind": kind, "key": key, "archived": True}


def entry(published, kind, key):
    return published.get("layouts" if kind == "layout" else "themes", {}).get(key)


def js_marker(kind, root=ROOT):
    path = Path(root) / ("assets/templates.js" if kind == "layout" else "assets/theme.js")
    marker = LAYOUT_MARKER if kind == "layout" else THEME_MARKER
    text = path.read_text(encoding="utf-8")
    if marker not in text:
        raise ValueError("注册表缺少插入标记 %s" % marker)
    return path, text, marker


def insert_js_entry(kind, key, item, root=ROOT):
    path, text, marker = js_marker(kind, root)
    if ('"%s":' % key) in text:
        raise ValueError("注册表已存在 key:%s" % key)
    if kind == "layout":
        payload = {
            "label": item["label"], "desc": item.get("desc", ""), "file": item["file"],
            "archetype": item.get("archetype", ""), "nav": item.get("nav", False),
            "lead": item.get("lead", False), "bands": item.get("bands", False),
            "sidebar": False, "toc": item.get("toc", False),
            "status": "published", "source": "AI",
        }
        line = "    \"%s\": %s," % (key, json.dumps(payload, ensure_ascii=False))
    else:
        line = "    \"%s\": {\"file\": %s, \"label\": %s}," % (
            key, json.dumps(item["file"].split("/")[-1], ensure_ascii=False),
            json.dumps(item["label"], ensure_ascii=False))
    return text.replace(marker, line + "\n    " + marker, 1)


def display_defaults(kind):
    if kind == "layout":
        return ["standard", "news", "magazine"]
    return ["default", "dark", "tech", "campus", "classical"]
