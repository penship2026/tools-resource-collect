#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""采集设置页的本地配置读写。

只服务 127.0.0.1 的设置页；不部署到 Pages。配置文件仍是仓库根的
sections.yml / topics.yml，保存后用 generate.py 的同一套校验重新验证。
"""

import json
import os
import re

import generate


SECTION_ID_RE = re.compile(r"[a-z0-9-]+")
RESERVED_SECTIONS = {
    "infant-care": (0, 36),
    "preschool": (36, 72),
    "k12": (72, 216),
}


def _string_list(value):
    return generate.keyword_list(value)


def _load_current():
    return generate.load_sections_yaml(), generate.load_topics_yaml(generate.TOPICS_FILE)


def normalize_sections(raw):
    """校验板块配置，返回 (sections, warnings)。不合法抛 ValueError。"""
    if not isinstance(raw, list) or not raw:
        raise ValueError("至少保留 7 个预设板块")
    sections, seen = [], set()
    for idx, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            raise ValueError("sections[%d] 必须是对象" % (idx - 1))
        sid = str(item.get("id") or "").strip()
        if not SECTION_ID_RE.fullmatch(sid):
            raise ValueError("sections[%d].id 非法：%s" % (idx - 1, sid))
        if sid in seen:
            raise ValueError("板块 id 重复：%s" % sid)
        seen.add(sid)
        title = str(item.get("title") or "").strip()
        if not 2 <= len(title) <= 12:
            raise ValueError("板块 %s 的 title 必须是 2–12 字" % sid)
        order = item.get("order")
        if not isinstance(order, int):
            raise ValueError("板块 %s 的 order 必须是整数" % sid)
        age_min = item.get("age_min_months")
        age_max = item.get("age_max_months")
        for age, label in ((age_min, "age_min_months"), (age_max, "age_max_months")):
            if age is not None and not isinstance(age, int):
                raise ValueError("板块 %s 的 %s 必须是整数或 null" % (sid, label))
        if (age_min is None) != (age_max is None):
            raise ValueError("板块 %s 的年龄段必须同时填写或同时为 null" % sid)
        if age_min is not None and age_min >= age_max:
            raise ValueError("板块 %s 的年龄段起点必须小于终点" % sid)
        enabled = item.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError("板块 %s 的 enabled 必须是布尔值" % sid)
        description = str(item.get("description") or "").strip()
        if len(description) > 60:
            raise ValueError("板块 %s 的 description 超过 60 字" % sid)
        sections.append({
            "id": sid, "title": title,
            "age_min_months": age_min, "age_max_months": age_max,
            "order": order, "enabled": enabled, "description": description,
        })

    for sid, bounds in RESERVED_SECTIONS.items():
        section = next((s for s in sections if s["id"] == sid), None)
        if not section:
            raise ValueError("保留板块不可删除：%s" % sid)
        if (section["age_min_months"], section["age_max_months"]) != bounds:
            raise ValueError("保留板块 %s 的年龄段必须是 %d–%d" % (sid, bounds[0], bounds[1]))
    for section in sections:
        if section["id"] not in RESERVED_SECTIONS and section["age_min_months"] is not None:
            raise ValueError("自定义板块 %s 只能全龄" % section["id"])
    # 自定义板块不能插进 0–18 的三段之间：order 必须排在所有保留板块之后或不影响三段连续性
    ordered = sorted((next(s for s in sections if s["id"] == sid) for sid in RESERVED_SECTIONS),
                     key=lambda s: s["age_min_months"])
    for left, right in zip(ordered, ordered[1:]):
        if left["age_max_months"] != right["age_min_months"]:
            raise ValueError("0–18 岁板块存在空档或重叠：%s / %s" % (left["id"], right["id"]))
    warnings = []
    for section in sections:
        if section["id"] not in RESERVED_SECTIONS and not section["description"]:
            warnings.append("自定义板块 %s 没有 description" % section["id"])
    return sections, warnings


def normalize_topics(raw, sections):
    """校验主题配置，返回 (topics, warnings)。"""
    if not isinstance(raw, list):
        raise ValueError("topics 必须是数组")
    valid_sections = {s["id"]: s for s in sections}
    topics, seen = [], set()
    for idx, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            raise ValueError("topics[%d] 必须是对象" % (idx - 1))
        tid = str(item.get("id") or "").strip()
        if not tid:
            raise ValueError("topics[%d].id 必填" % (idx - 1))
        if not generate.valid_unit_id(tid):
            raise ValueError("主题 id 非法：%s" % tid)
        if tid in seen:
            raise ValueError("主题 id 重复：%s" % tid)
        seen.add(tid)
        section = str(item.get("section") or "").strip()
        if section not in valid_sections:
            raise ValueError("主题 %s 的 section 不存在：%s" % (tid, section))
        title = str(item.get("title") or "").strip()
        if not title:
            raise ValueError("主题 %s 缺少 title" % tid)
        must = _string_list(item.get("must_keywords"))
        if not 1 <= len(must) <= 4:
            raise ValueError("主题 %s 的 must_keywords 必须是 1–4 个" % tid)
        any_list = _string_list(item.get("any_keywords"))
        if len(any_list) > 5:
            raise ValueError("主题 %s 的 any_keywords 最多 5 个" % tid)
        channels = _string_list(item.get("channels")) or ["bilibili"]
        unknown = [c for c in channels if c not in generate.channels_valid()]
        if unknown:
            raise ValueError("主题 %s 的渠道不支持：%s" % (tid, ", ".join(unknown)))
        enabled = item.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError("主题 %s 的 enabled 必须是布尔值" % tid)
        topics.append({
            "id": tid, "section": section, "title": title,
            "must_keywords": must, "any_keywords": any_list,
            "channels": channels, "enabled": enabled,
        })
    warnings = []
    for section in sections:
        if not section["enabled"]:
            continue
        if not any(t["section"] == section["id"] and t["enabled"] for t in topics):
            warnings.append("板块 %s 已启用但没有启用主题，不会参与自动采集" % section["title"])
    return topics, warnings


def _q(value):
    return json.dumps(str(value), ensure_ascii=False)


def _yaml_list(values):
    return "[" + ", ".join(_q(x) for x in values) + "]"


def dump_sections(sections):
    lines = ["version: 1", "", "# 内容板块注册表（公开配置，由采集设置页维护）", "", "sections:"]
    for section in sections:
        lines += [
            "  - id: %s" % section["id"],
            "    title: %s" % _q(section["title"]),
            "    age_min_months: %s" % ("null" if section["age_min_months"] is None else section["age_min_months"]),
            "    age_max_months: %s" % ("null" if section["age_max_months"] is None else section["age_max_months"]),
            "    order: %d" % section["order"],
            "    enabled: %s" % ("true" if section["enabled"] else "false"),
            "    description: %s" % _q(section.get("description") or ""),
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def dump_topics(topics):
    lines = [
        "version: 1", "",
        "# 定时采集的主题清单（公开配置，由采集设置页维护）",
        "# 一个主题对应一个采集单元；must 全部命中 + any 至少命中一个。", "",
        "topics:",
    ]
    for topic in topics:
        lines += [
            "  - id: %s" % topic["id"],
            "    section: %s" % topic["section"],
            "    title: %s" % _q(topic["title"]),
            "    must_keywords: %s" % _yaml_list(topic["must_keywords"]),
            "    any_keywords: %s" % _yaml_list(topic.get("any_keywords") or []),
            "    channels: %s" % _yaml_list(topic.get("channels") or ["bilibili"]),
            "    enabled: %s" % ("true" if topic.get("enabled", True) else "false"),
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def save_settings(payload):
    """原子保存 sections.yml / topics.yml，并用 --verify 二次确认。"""
    sections, warnings_s = normalize_sections(payload.get("sections"))
    topics, warnings_t = normalize_topics(payload.get("topics"), sections)
    # 先写临时前的完整文本；任一文件写入失败不留下半截（write_text_atomic 负责）
    generate.write_text_atomic(generate.SECTIONS_FILE, dump_sections(sections), snapshot=True)
    generate.write_text_atomic(generate.TOPICS_FILE, dump_topics(topics), snapshot=True)
    result = generate.verify_data(log=lambda *a: None)
    if not result["ok"]:
        raise ValueError("保存后校验失败: " + "；".join(result["problems"]))
    return {
        "ok": True,
        "sections": sections,
        "topics": topics,
        "warnings": warnings_s + warnings_t,
        "verify": result,
    }


def public_settings():
    sections = generate.load_sections_yaml()
    topics = generate.load_topics_yaml(generate.TOPICS_FILE)
    return {
        "ok": True,
        "sections": sections,
        "topics": topics,
        "schedule": actions_schedule(),
    }


def _read_workflow():
    path = os.path.join(generate.ROOT, ".github", "workflows", "update-data.yml")
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def actions_schedule():
    text = _read_workflow()
    cron = ""
    pages = 3
    match = re.search(r'cron:\s*"([^"]+)"', text)
    if match:
        cron = match.group(1)
    match = re.search(r"pages:\s*\n(?:.*\n)*?.*default:\s*\"?([0-9]+)\"?", text)
    if match:
        pages = int(match.group(1))
    return {
        "cron": cron,
        "beijing": "每天 07:00" if cron == "0 23 * * *" else "以 workflow 为准",
        "pages": pages,
        "source": ".github/workflows/update-data.yml",
        "mode": "actions",
    }


def export_cron():
    schedule = actions_schedule()
    cron = schedule["cron"] or "0 23 * * *"
    text = "\n".join([
        "# 复制到 .github/workflows/update-data.yml 的 on.schedule",
        "on:",
        "  schedule:",
        '    - cron: "%s"' % cron,
        "  workflow_dispatch:",
    ])
    return {"ok": True, "cron_text": text, "cron": cron, "beijing": schedule["beijing"]}
