#!/usr/bin/env python3
"""A4 AI 设计管理处：展示清单上下架、5 套上限与标准项锁定。"""
from __future__ import annotations

from pathlib import Path

import registry
import site_store

ROOT = Path(__file__).resolve().parents[2]
KINDS = ("layout", "theme")


class DisplayError(RuntimeError):
    def __init__(self, code, message, details=None):
        self.code = code
        self.details = details or {}
        super().__init__(message)

    def as_dict(self):
        return {"ok": False, "code": self.code, "message": str(self), **self.details}


def _visible_key(kind):
    return "visible_layouts" if kind == "layout" else "visible_themes"


def _limit_key(kind):
    return "max_layouts" if kind == "layout" else "max_themes"


def manage_payload(root=ROOT):
    visible = site_store.read_display(root)
    out = {}
    for kind in KINDS:
        items = registry.items(kind, root)
        keys = visible[_visible_key(kind)]
        out[kind] = {
            "count": len(keys), "max": visible[_limit_key(kind)],
            "locked": registry.LAYOUT_LOCK if kind == "layout" else registry.THEME_LOCK,
            "items": [dict(item, visible=key in keys) for key, item in sorted(items.items())],
        }
    return {"ok": True, "visible": visible, "kinds": out}


def set_visible(kind, key, on, root=ROOT):
    if kind not in KINDS:
        raise DisplayError("DISPLAY_KIND", "kind 必须是 layout/theme")
    items = registry.items(kind, root)
    if key not in items:
        raise DisplayError("DISPLAY_UNKNOWN", "设计不存在:%s" % key)
    if on and items[key].get("archived"):
        raise DisplayError("DISPLAY_ARCHIVED", "已归档的模板不能直接上架，请先克隆新版本")
    locked = registry.LAYOUT_LOCK if kind == "layout" else registry.THEME_LOCK
    if not on and key == locked:
        raise DisplayError("DISPLAY_LOCKED", "%s 为锁定项，不能下架" % locked)
    visible = site_store.read_display(root)
    target = visible[_visible_key(kind)]
    limit = visible[_limit_key(kind)]
    if on:
        if key in target:
            return {"ok": True, "changed": False, "visible": visible}
        if len(target) >= limit:
            raise DisplayError("DISPLAY_FULL", "展示已满 %d 套，先下架一套或提高上限" % limit)
        target.append(key)
    else:
        if key not in target:
            return {"ok": True, "changed": False, "visible": visible}
        target.remove(key)
    if locked not in target:
        raise DisplayError("DISPLAY_LOCKED", "展示清单必须保留 %s" % locked)
    new_visible = site_store.write_display(
        visible["visible_layouts"], visible["visible_themes"], root,
        max_layouts=visible["max_layouts"], max_themes=visible["max_themes"])
    return {"ok": True, "changed": True, "visible": new_visible}


def set_limit(kind, max_items, root=ROOT):
    if kind not in KINDS:
        raise DisplayError("DISPLAY_KIND", "kind 必须是 layout/theme")
    try:
        max_items = int(max_items)
    except (TypeError, ValueError):
        raise DisplayError("DISPLAY_LIMIT", "上限必须是整数")
    if max_items < 1 or max_items > site_store.MAX_LIMIT:
        raise DisplayError("DISPLAY_LIMIT", "上限必须在 1–%d 之间" % site_store.MAX_LIMIT)
    visible = site_store.read_display(root)
    if max_items < len(visible[_visible_key(kind)]):
        raise DisplayError("DISPLAY_LIMIT_TOO_SMALL", "当前展示已超过新上限，先下架")
    visible[_limit_key(kind)] = max_items
    new_visible = site_store.write_display(
        visible["visible_layouts"], visible["visible_themes"], root,
        max_layouts=visible["max_layouts"], max_themes=visible["max_themes"])
    return {"ok": True, "changed": True, "kind": kind, "max": max_items, "visible": new_visible}


def reorder(kind, key, direction, root=ROOT):
    if kind not in KINDS:
        raise DisplayError("DISPLAY_KIND", "kind 必须是 layout/theme")
    if direction not in (-1, 1):
        raise DisplayError("DISPLAY_DIRECTION", "direction 只能是 -1/1")
    visible = site_store.read_display(root)
    target = visible[_visible_key(kind)]
    if key not in target:
        raise DisplayError("DISPLAY_HIDDEN", "只允许调整展示中的设计")
    index = target.index(key)
    new_index = index + direction
    if new_index < 0 or new_index >= len(target):
        return {"ok": True, "changed": False, "visible": visible}
    target[index], target[new_index] = target[new_index], target[index]
    new_visible = site_store.write_display(
        visible["visible_layouts"], visible["visible_themes"], root,
        max_layouts=visible["max_layouts"], max_themes=visible["max_themes"])
    return {"ok": True, "changed": True, "visible": new_visible}
