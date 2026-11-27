#!/usr/bin/env python3
"""A2 生成管线：合成样例 → 模型/mock → 3 个候选 Spec → 校验 → 编译 → 草稿。

安全边界：
- 默认只发合成样例；不读取 jiye.mine.v1、采集正文、作者主页、来源链接。
- 模型输出只做 JSON 解析和 schema 校验，绝不 eval，绝不直接写 CSS。
- 无 Key 时降级 mock，产物标记 source=mock，不能当可上线模板。
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

import compiler  # noqa: E402
from adapters import mock as mock_adapter  # noqa: E402
from adapters import openai_compat  # noqa: E402

PROMPT_DIR = HERE / "prompts"
CACHE_DIR = HERE / "cache"
DRAFT_DIR = HERE / "drafts"
SAMPLE_ID = "synthetic-preview-v1"

# 只含虚构标题、标签、板块与数量；不含收藏、作者、链接、简介原文。
SAMPLE = {
    "id": SAMPLE_ID,
    "description": "固定合成样例，仅用于 prompt；不是真实收藏",
    "sections": [
        {"name": "AI 与工具", "count": 12},
        {"name": "设计", "count": 9},
        {"name": "摄影", "count": 7},
        {"name": "学习", "count": 6},
        {"name": "生活", "count": 4},
        {"name": "开发", "count": 8},
        {"name": "空板块", "count": 0}
    ],
    "titles": [
        "AI 工具工作流", "版式设计基础", "街头摄影 8 讲",
        "学习方法整理", "生活整理术", "前端开发笔记"
    ],
    "tags": ["AI", "效率", "设计", "CSS", "学习", "整理"],
    "platforms": ["B站", "公众号", "小红书", "多平台"],
    "unit_types": {"series": 5, "single": 1}
}


class GenerationError(RuntimeError):
    def __init__(self, errors, raw=""):
        self.errors = list(errors)
        self.raw = raw
        super().__init__("; ".join(self.errors))


class CandidateError(ValueError):
    pass


def read_prompt(name):
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def read_system(kind):
    if kind == "layout":
        return read_prompt("system-layout.md")
    if kind == "theme":
        return read_prompt("system-theme.md")
    raise GenerationError(["未知 kind: %s" % kind])


def build_user_prompt(kind, request, constraints="", sample=None):
    sample = sample or SAMPLE
    template = read_prompt("generate.md")
    return (template
            .replace("{{KIND}}", kind)
            .replace("{{SAMPLE}}", "```json\n%s\n```" % json.dumps(sample, ensure_ascii=False, indent=2))
            .replace("{{REQUEST}}", str(request or "").strip())
            .replace("{{CONSTRAINTS}}", str(constraints or "无额外约束").strip()))


def build_revise_prompt(spec, comments, metrics=""):
    template = read_prompt("revise.md")
    return (template
            .replace("{{SPEC}}", json.dumps(spec, ensure_ascii=False, indent=2))
            .replace("{{COMMENTS}}", str(comments or "").strip())
            .replace("{{METRICS}}", str(metrics or "无").strip()))


def _strip_fence(text):
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()


def parse_candidates(text):
    text = _strip_fence(text)
    start = text.find("[")
    end = text.rfind("]")
    obj_start = text.find("{")
    if start >= 0 and end > start:
        payload = text[start:end + 1]
    elif obj_start >= 0:
        payload = text[obj_start:]
    else:
        raise CandidateError("模型输出里没有 JSON 数组/对象")
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise CandidateError("模型输出不是合法 JSON:%s" % exc)
    if isinstance(data, dict):
        data = data.get("candidates") or data.get("items")
    if not isinstance(data, list):
        raise CandidateError("候选必须是 JSON 数组")
    return data


def validate_candidates(items, kind, expect=3):
    errors = []
    if not isinstance(items, list) or len(items) != expect:
        errors.append("候选数量必须是 %d，实际 %s" % (expect, len(items) if isinstance(items, list) else "非数组"))
        return errors
    keys = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append("candidate-%d 不是对象" % (i + 1))
            continue
        if item.get("kind") != kind:
            errors.append("candidate-%d kind 必须是 %s" % (i + 1, kind))
        errs = compiler.validate_layout_spec(item) if kind == "layout" else compiler.validate_theme_spec(item)
        for err in errs:
            errors.append("candidate-%d %s" % (i + 1, err))
        if item.get("key"):
            keys.append(item["key"])
    if len(keys) != len(set(keys)):
        errors.append("候选 key 重复")
    return errors


def diversity_errors(items, kind):
    if kind == "layout":
        sigs = [(x["bands"]["columns"], x["cards"]["coverRatio"], x["hero"]["type"], x["density"]) for x in items]
        labels = ("列数", "封面比例", "首屏类型", "密度")
    else:
        sigs = [(x["tokens"]["--brand"], x["tokens"]["--bg"], x["tokens"]["--font-display"], x["tokens"]["--radius"]) for x in items]
        labels = ("主色", "背景", "字体", "圆角")
    errors = []
    for i in range(len(sigs)):
        for j in range(i + 1, len(sigs)):
            diff = sum(1 for a, b in zip(sigs[i], sigs[j]) if a != b)
            if diff < 2:
                errors.append("candidate-%d 与 candidate-%d 只差 %d 个维度（要求 ≥2）：%s" % (
                    i + 1, j + 1, diff, " / ".join(labels)))
    return errors


def _now():
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def _cache_key(kind, system, user, model):
    raw = "\n".join((kind, system, user, model)).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_cache(path):
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data.get("text"), str):
            return data
    except (ValueError, OSError):
        return None
    return None


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def choose_adapter(mock=False, adapter=None):
    if adapter is not None:
        return adapter
    if mock:
        return mock_adapter.MockAdapter()
    real = openai_compat.from_env()
    if real:
        return real
    return mock_adapter.MockAdapter()


def generate(kind, request, constraints="", mock=False, adapter=None, out_dir=None,
             cache_dir=None, use_cache=True, expect=3, attempts=2):
    if kind not in ("layout", "theme"):
        raise GenerationError(["kind 必须是 layout / theme"])
    system = read_system(kind)
    user = build_user_prompt(kind, request, constraints)
    chosen = choose_adapter(mock=mock, adapter=adapter)
    model = getattr(chosen, "model", "unknown")
    source = getattr(chosen, "source", "model")
    cache_path = Path(cache_dir or CACHE_DIR) / (_cache_key(kind, system, user, model) + ".json")
    cache_hit = False
    cached = _read_cache(cache_path) if use_cache else None
    if cached:
        raw = cached["text"]
        cache_hit = True
    else:
        raw = None

    last_raw = raw or ""
    errors = []
    items = None
    for attempt in range(1, attempts + 1):
        if not cache_hit or attempt > 1:
            raw = chosen.complete(system, user, kind=kind)
            last_raw = raw
        try:
            items = parse_candidates(raw)
            errors = validate_candidates(items, kind, expect=expect)
            if not errors:
                errors = diversity_errors(items, kind)
            if not errors:
                break
        except CandidateError as exc:
            errors = [str(exc)]
        if attempt < attempts:
            cache_hit = False
    if errors or not items:
        raise GenerationError(errors or ["生成失败"], last_raw)

    if use_cache and not cache_hit:
        _write_json(cache_path, {"text": raw, "model": model, "source": source,
                                 "created_at": _now(), "prompt_sha256": cache_path.stem})

    out = Path(out_dir or DRAFT_DIR)
    out.mkdir(parents=True, exist_ok=True)
    records = []
    for i, item in enumerate(items):
        key = item["key"]
        result = compiler.compile_spec(item, kind=kind, no_timestamp=True)
        candidate_dir = out / key / ("candidate-%d" % (i + 1))
        candidate_dir.mkdir(parents=True, exist_ok=True)
        _write_json(candidate_dir / "spec.json", item)
        (candidate_dir / ("%s.css" % key)).write_text(result["css"], encoding="utf-8")
        _write_json(candidate_dir / ("%s.registry.json" % key), result["registry"])
        records.append({
            "key": key,
            "name": item["name"],
            "kind": kind,
            "dir": str(candidate_dir.relative_to(out)) if candidate_dir.is_relative_to(out) else str(candidate_dir),
            "css": str((candidate_dir / ("%s.css" % key)).relative_to(out)),
            "css_bytes": len(result["css"].encode("utf-8")),
        })

    run = {
        "ok": True,
        "kind": kind,
        "source": source,
        "model": model,
        "cache_hit": cache_hit,
        "request": str(request or "").strip(),
        "constraints": str(constraints or "").strip(),
        "sample_id": SAMPLE_ID,
        "created_at": _now(),
        "prompt_sha256": cache_path.stem,
        "candidates": records,
    }
    _write_json(out / "run.json", run)
    return run
