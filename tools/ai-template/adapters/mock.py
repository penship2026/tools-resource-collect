"""离线 mock 适配器：只用于 CI / 无 Key 时走通全链路，产物不得当可上线模板。"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import compiler

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
LAYOUT_FIXTURE = ROOT / "tests" / "fixtures" / "specs" / "layout-news-dense.json"
THEME_FIXTURE = ROOT / "tests" / "fixtures" / "specs" / "theme-mist.json"


def _load(path):
    return compiler.load_json(path)


def layout_candidates():
    base = _load(LAYOUT_FIXTURE)
    variants = [
        ("news-dense", "门户 · 紧凑", "4 列紧凑门户，适合一屏扫完 6 个板块", 4, "4:3", "lead", "compact", 3),
        ("news-tiles", "门户 · 方图", "4 列方图，适合截图类内容", 4, "1:1", "text", "comfortable", 2),
        ("news-brief", "门户 · 简讯", "2 列简讯，窄屏优先", 2, "16:9", "text", "compact", 0),
    ]
    out = []
    for key, name, intent, cols, cover, hero, density, subs in variants:
        item = copy.deepcopy(base)
        item["key"] = key
        item["name"] = name
        item["intent"] = intent
        item["density"] = density
        item["hero"]["type"] = hero
        item["hero"]["subCards"] = subs
        item["bands"]["columns"] = cols
        item["bands"]["rows"] = 1
        item["bands"]["showDescription"] = bool(subs)
        item["bands"]["moreLink"] = cols >= 3
        item["cards"]["coverRatio"] = cover
        item["cards"]["showTags"] = cols >= 3
        item["rationale"] = [
            "固定 mock 候选 %s，只用于离线链路" % key,
            "%d 列与 %s 封面形成结构差异" % (cols, cover),
            "密度选择 %s，验证编译与预览" % density,
        ]
        out.append(item)
    return out


def theme_candidates():
    base = _load(THEME_FIXTURE)
    variants = [
        ("mist", "雾青", "低饱和青绿，浅色阅读", "light", {
            "--bg": "#f6f8f4", "--surface": "#ffffff", "--text": "#1f2a24",
            "--text-sub": "#4d5d54", "--brand": "#2f6f4e", "--brand-soft": "#e6f1ea",
            "--brand-2": "#7aa98d", "--radius": "18px",
        }),
        ("clay", "陶土", "暖陶土色，纸张质感", "light", {
            "--bg": "#fbf7f1", "--surface": "#fffdf9", "--text": "#2c2620",
            "--text-sub": "#5f554a", "--brand": "#8a4f2d", "--brand-soft": "#f3e3d6",
            "--brand-2": "#b07a54", "--radius": "8px",
        }),
        ("ink", "墨夜", "深墨绿夜间阅读", "dark", {
            "--bg": "#0f1412", "--surface": "#17201c", "--text": "#e8efea",
            "--text-sub": "#b7c5bc", "--brand": "#8fc7a4", "--brand-soft": "#1e3328",
            "--brand-2": "#5c8a70", "--radius": "16px",
        }),
    ]
    out = []
    for key, name, intent, mode, tokens in variants:
        item = copy.deepcopy(base)
        item["key"] = key
        item["name"] = name
        item["intent"] = intent
        item["mode"] = mode
        for token, value in tokens.items():
            item["tokens"][token] = value
        item["tokens"]["--header-bg"] = "rgba(255, 255, 255, .86)" if mode == "light" else "rgba(15, 20, 18, .86)"
        item["tokens"]["--hero-wash"] = (
            "linear-gradient(180deg, #ffffff, #f6f8f4)" if mode == "light"
            else "linear-gradient(180deg, #17201c, #0f1412)"
        )
        item["rationale"] = [
            "固定 mock 候选 %s，只用于离线链路" % key,
            "主色与背景明度形成差异",
            "圆角 %s 与字体保持可读" % tokens["--radius"],
        ]
        out.append(item)
    return out


def complete(system, user, kind=None):
    if kind is None:
        kind = "theme" if "29 个 token" in (system or "") or "主题设计" in (system or "") else "layout"
    items = theme_candidates() if kind == "theme" else layout_candidates()
    return json.dumps(items, ensure_ascii=False, indent=2)


class MockAdapter:
    source = "mock"
    model = "mock"

    def complete(self, system, user, kind=None):
        return complete(system, user, kind)
