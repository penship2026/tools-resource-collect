#!/usr/bin/env python3
"""二期 A1 双编译器：版式 Spec / 主题 Spec → CSS + 注册表草稿。

约束：
- 不引入 jsonschema / 模板引擎 / Playwright；只用标准库。
- 版式只允许 nav / lead / bands / toc；主题只允许 29 个既有 token。
- 默认不写时间戳，保证同一 Spec 两次编译字节一致；需要留痕时用 --timestamp。
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC_DIR = ROOT / "spec"
LAYOUT_SCHEMA = SPEC_DIR / "layout.schema.json"
THEME_SCHEMA = SPEC_DIR / "theme.schema.json"
LAYOUT_DIR = ROOT / "assets" / "layouts"

TOKEN_ORDER = [
    "--bg", "--surface", "--text", "--text-sub", "--text-mute", "--border",
    "--brand", "--brand-soft", "--shadow", "--radius", "--radius-sm", "--radius-pill",
    "--font-sans", "--font-display", "--fs-hero", "--fs-title", "--fs-body", "--fs-sm",
    "--fs-xs", "--gap-card", "--pad-card", "--shadow-hover", "--brand-2", "--hero-wash",
    "--header-bg", "--plat-bilibili", "--plat-wechat", "--plat-xhs", "--plat-multi",
]

CAPABILITIES = {
    "standard": {"nav": False, "lead": False, "bands": False, "toc": False},
    "news": {"nav": True, "lead": True, "bands": True, "toc": False},
    "magazine": {"nav": True, "lead": False, "bands": True, "toc": True},
}
DENSITY = {
    "comfortable": {"gap": 20, "pad": 20, "section": 56},
    "compact": {"gap": 14, "pad": 14, "section": 40},
}
COLOR_LITERAL = re.compile(
    r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b"
    r"|(?:rgb|hsl)a?\([^)]*\)"
)


class SpecError(ValueError):
    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


def load_json(path):
    path = Path(path)
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _type_ok(value, expected):
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return True


def validate(spec, schema, path="spec"):
    """JSON Schema 子集校验：够 A0/A1 的 schema 用，错误一次收全。"""
    errors = []

    def err(p, message):
        errors.append("%s: %s" % (p, message))

    def walk(value, node, p):
        if not isinstance(node, dict):
            return
        if "const" in node and value != node["const"]:
            err(p, "必须为 %r" % node["const"])
        if "enum" in node and value not in node["enum"]:
            err(p, "必须是 %s 之一" % " / ".join(str(x) for x in node["enum"]))
        expected = node.get("type")
        if expected and not _type_ok(value, expected):
            err(p, "类型必须是 %s" % expected)
            return
        if isinstance(value, str):
            if "minLength" in node and len(value) < node["minLength"]:
                err(p, "长度不能少于 %d" % node["minLength"])
            if "maxLength" in node and len(value) > node["maxLength"]:
                err(p, "长度不能超过 %d" % node["maxLength"])
            if "pattern" in node and not re.search(node["pattern"], value):
                err(p, "不符合格式 %s" % node["pattern"])
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in node and value < node["minimum"]:
                err(p, "不能小于 %s" % node["minimum"])
            if "maximum" in node and value > node["maximum"]:
                err(p, "不能大于 %s" % node["maximum"])
        if isinstance(value, list):
            if "minItems" in node and len(value) < node["minItems"]:
                err(p, "至少 %d 项" % node["minItems"])
            if "maxItems" in node and len(value) > node["maxItems"]:
                err(p, "最多 %d 项" % node["maxItems"])
            if node.get("uniqueItems") and len({json.dumps(v, sort_keys=True) for v in value}) != len(value):
                err(p, "不能重复")
            if "items" in node:
                for i, item in enumerate(value):
                    walk(item, node["items"], "%s[%d]" % (p, i))
        if isinstance(value, dict):
            required = node.get("required") or []
            for key in required:
                if key not in value:
                    err(p, "缺少 %s" % key)
            props = node.get("properties") or {}
            if node.get("additionalProperties") is False:
                for key in value:
                    if key not in props:
                        err(p, "不允许字段 %s" % key)
            for key, child in props.items():
                if key in value:
                    walk(value[key], child, "%s.%s" % (p, key))

    walk(spec, schema, path)
    return errors


def validate_layout_spec(spec):
    return validate(spec, load_json(LAYOUT_SCHEMA), "layout")


def validate_theme_spec(spec):
    return validate(spec, load_json(THEME_SCHEMA), "theme")


def _format_num(value):
    value = round(float(value), 2)
    return ("%.2f" % value).rstrip("0").rstrip(".")


def _ratio(value):
    a, b = str(value).split(":")
    return "%s / %s" % (a, b)


def _header(kind, spec, approval, timestamp):
    lines = [
        "/* 集页 · AI %s: %s" % ("版式" if kind == "layout" else "主题", spec["key"]),
        " * name: %s" % spec["name"],
        " * intent: %s" % spec["intent"],
        " * spec sha256: %s" % hashlib.sha256(
            json.dumps(spec, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    ]
    if approval:
        lines.append(" * approval: %s" % approval)
    if timestamp:
        lines.append(" * generated: %s" % timestamp)
    lines.append(" */")
    return "\n".join(lines)


def _strip_literal_colors(css):
    """版式基座不携带直接颜色；把历史遗留的 #hex / rgb() 收敛到主题 token。"""
    return COLOR_LITERAL.sub("var(--brand)", css)


def compile_layout(spec, no_timestamp=True, approval="", timestamp=None):
    errors = validate_layout_spec(spec)
    if errors:
        raise SpecError(errors)
    key = spec["key"]
    archetype = spec["archetype"]
    caps = CAPABILITIES[archetype]
    density = DENSITY[spec["density"]]
    base_path = LAYOUT_DIR / ("%s.css" % archetype)
    base = base_path.read_text(encoding="utf-8")
    base = base.replace('html[data-layout="%s"]' % archetype, 'html[data-layout="%s"]' % key)
    base = _strip_literal_colors(base)

    ratio = _format_num(spec["hero"]["mainRatio"])
    rest = _format_num(1 - spec["hero"]["mainRatio"])
    cover = _ratio(spec["cards"]["coverRatio"])
    cols = spec["bands"]["columns"]
    mobile = spec["responsive"]["mobileColumns"]
    lines = [_header("layout", spec, approval, None if no_timestamp else timestamp)]
    lines += [base.rstrip(), "", "/* --- spec overrides --- */"]
    lines += [
        'html[data-layout="%s"] {' % key,
        "  --layout-band-cols: %d;" % cols,
        "  --layout-cover-ratio: %s;" % cover,
        "  --layout-grid-gap: %dpx;" % density["gap"],
        "  --layout-card-pad: %dpx;" % density["pad"],
        "  --layout-section-gap: %dpx;" % density["section"],
        "}",
    ]
    sel = 'html[data-layout="%s"]' % key
    if not caps["nav"] or spec["nav"]["style"] == "none":
        lines.append("%s .section-nav { display: none; }" % sel)
    elif not spec["nav"]["sticky"]:
        lines.append("%s .section-nav { position: static; }" % sel)
    if not caps["lead"] or spec["hero"]["type"] != "lead":
        lines.append("%s .lead { display: none; }" % sel)
    else:
        lines.append("%s .lead { grid-template-columns: minmax(0, %sfr) minmax(0, %sfr); }" % (sel, ratio, rest))
        if spec["hero"]["subCards"] == 0:
            lines.append("%s .lead-side { display: none; }" % sel)
        elif spec["hero"]["subCards"] < 3:
            lines.append("%s .lead-side .lead-mini:nth-child(n+%d) { display: none; }" % (
                sel, spec["hero"]["subCards"] + 1))
    if not spec["bands"]["showDescription"]:
        lines.append("%s .topic-card .slogan { display: none; }" % sel)
    if not spec["bands"]["moreLink"]:
        lines.append("%s .band-more { display: none; }" % sel)
    if not spec["cards"]["showTags"]:
        lines.append("%s .topic-card .tag-line { display: none; }" % sel)
    if not spec["responsive"]["leadStack"]:
        lines.append("%s .lead { grid-template-columns: minmax(0, 1fr); }" % sel)
    lines += [
        "@media (max-width: %dpx) {" % spec["responsive"]["breakpoints"][0],
        "  %s .topic-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }" % sel,
        "}",
        "@media (max-width: %dpx) {" % spec["responsive"]["breakpoints"][1],
        "  %s .topic-grid { grid-template-columns: repeat(%d, minmax(0, 1fr)); }" % (sel, mobile),
        "  %s .lead { grid-template-columns: minmax(0, 1fr); }" % sel,
        "}",
        "@media (max-width: %dpx) {" % spec["responsive"]["breakpoints"][2],
        "  %s .topic-grid { grid-template-columns: minmax(0, 1fr); }" % sel,
        "}",
    ]
    css = "\n".join(lines).rstrip() + "\n"
    _assert_layout_budget(css, spec)
    return css


def _assert_layout_budget(css, spec):
    errors = []
    if len(css.encode("utf-8")) > spec["limits"]["maxCssKb"] * 1024:
        errors.append("CSS 超过 %sKB" % spec["limits"]["maxCssKb"])
    if css.count("{") > spec["limits"]["maxRules"]:
        errors.append("规则数超过 %s" % spec["limits"]["maxRules"])
    for bad in ("!important", "@import", "url("):
        if bad in css:
            errors.append("出现禁用内容 %s" % bad)
    if COLOR_LITERAL.search(css):
        errors.append("出现直接颜色")
    if errors:
        raise SpecError(errors)


def compile_theme(spec, no_timestamp=True, approval="", timestamp=None):
    errors = validate_theme_spec(spec)
    if errors:
        raise SpecError(errors)
    lines = [_header("theme", spec, approval, None if no_timestamp else timestamp), ":root {"]
    lines.append("  color-scheme: %s;" % spec["mode"])
    for token in TOKEN_ORDER:
        lines.append("  %s: %s;" % (token, spec["tokens"][token]))
    lines.append("}")
    css = "\n".join(lines).rstrip() + "\n"
    if len(css.encode("utf-8")) > spec["limits"]["maxCssKb"] * 1024:
        raise SpecError(["CSS 超过 %sKB" % spec["limits"]["maxCssKb"]])
    if css.count("{") > spec["limits"]["maxRules"]:
        raise SpecError(["规则数超过 %s" % spec["limits"]["maxRules"]])
    return css


def layout_registry(spec, filename=None):
    caps = CAPABILITIES[spec["archetype"]]
    return {
        "label": spec["name"],
        "desc": spec["intent"],
        "file": filename or "assets/layouts/%s.css" % spec["key"],
        "archetype": spec["archetype"],
        "nav": caps["nav"],
        "lead": caps["lead"],
        "bands": caps["bands"],
        "sidebar": False,
        "toc": caps["toc"],
        "status": "published",
    }


def theme_registry(spec, filename=None):
    return {
        "label": spec["name"],
        "file": filename or "assets/themes/%s.css" % spec["key"],
        "status": "published",
    }


def compile_spec(spec, kind=None, no_timestamp=True, approval="", timestamp=None):
    kind = kind or spec.get("kind")
    if kind == "layout":
        return {"kind": "layout", "css": compile_layout(spec, no_timestamp, approval, timestamp),
                "registry": layout_registry(spec)}
    if kind == "theme":
        return {"kind": "theme", "css": compile_theme(spec, no_timestamp, approval, timestamp),
                "registry": theme_registry(spec)}
    raise SpecError(["未知 kind: %s" % kind])


def now_iso():
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
