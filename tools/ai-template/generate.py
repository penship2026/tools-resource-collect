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


def read_system(kind, count=3):
    if kind == "layout":
        text = read_prompt("system-layout.md")
    elif kind == "theme":
        text = read_prompt("system-theme.md")
    else:
        raise GenerationError(["未知 kind: %s" % kind])
    if count == 1:
        text = text.replace(
            "只输出**一个 JSON 数组**，恰好 3 个候选，每个候选是一个合法版式 Spec。",
            "只输出**一个 JSON 对象**，恰好 1 个候选，是一个合法版式 Spec。")
        text = text.replace(
            "只输出**一个 JSON 数组**，恰好 3 个候选，每个候选是一个合法主题 Spec。",
            "只输出**一个 JSON 对象**，恰好 1 个候选，是一个合法主题 Spec。")
        text = text.replace("三个候选", "候选")
    elif count != 3:
        text = text.replace("恰好 3 个候选", "恰好 %d 个候选" % count)
        text = text.replace("三个候选", "候选")
    return text


def build_user_prompt(kind, request, constraints="", sample=None, count=3):
    sample = sample or SAMPLE
    template = read_prompt("generate.md")
    return (template
            .replace("{{KIND}}", kind)
            .replace("{{SAMPLE}}", "```json\n%s\n```" % json.dumps(sample, ensure_ascii=False, indent=2))
            .replace("{{REQUEST}}", str(request or "").strip())
            .replace("{{CONSTRAINTS}}", str(constraints or "无额外约束").strip())
            .replace("设计 3 个候选", "设计 %d 个候选" % count)
            .replace("三个候选", "候选"))


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
    starts = [pos for pos in (text.find("["), text.find("{")) if pos >= 0]
    if not starts:
        raise CandidateError("模型输出里没有 JSON 数组/对象")
    start = min(starts)
    try:
        # 只取第一个完整 JSON 值，容忍模型在 JSON 后追加说明或第二个对象。
        data, _end = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError as exc:
        raise CandidateError("模型输出不是合法 JSON:%s" % exc)
    if isinstance(data, dict):
        data = data.get("candidates") or data.get("items") or [data]
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
    try:
        expect = int(expect)
    except (TypeError, ValueError):
        raise GenerationError(["候选数量必须是 1–5 的整数"])
    if expect < 1 or expect > 5:
        raise GenerationError(["候选数量必须在 1–5 之间"])
    system = read_system(kind, expect)
    user = build_user_prompt(kind, request, constraints, count=expect)
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


def regenerate(spec_path, comments, metrics="", mock=False, adapter=None, out_dir=None,
               cache_dir=None, use_cache=True, attempts=2):
    """按评审意见生成同 key 的新版本候选；旧候选不覆盖。"""
    path = Path(spec_path)
    spec = json.loads(path.read_text(encoding="utf-8"))
    kind = spec.get("kind")
    key = spec.get("key")
    if kind not in ("layout", "theme") or not key:
        raise GenerationError(["候选 spec 缺少 kind/key"])
    if not str(comments or "").strip():
        raise GenerationError(["迭代意见不能为空"])
    system = read_system(kind, 1)
    user = build_revise_prompt(spec, comments, metrics)
    chosen = choose_adapter(mock=mock, adapter=adapter)
    model = getattr(chosen, "model", "unknown")
    source = getattr(chosen, "source", "model")
    cache_path = Path(cache_dir or CACHE_DIR) / (_cache_key(kind, system, user, model) + ".json")
    cached = _read_cache(cache_path) if use_cache else None
    cache_hit = bool(cached)
    raw = cached["text"] if cached else ""
    last_raw = raw
    errors = []
    items = None
    for attempt in range(1, attempts + 1):
        if not cache_hit or attempt > 1:
            raw = chosen.complete(system, user, kind=kind)
            last_raw = raw
        try:
            items = parse_candidates(raw)
            errors = validate_candidates(items, kind, expect=1)
            if not errors and str(items[0].get("key")) != str(key):
                errors = ["迭代必须保持 key=%s，模型返回 %s" % (key, items[0].get("key"))]
            if not errors:
                break
        except CandidateError as exc:
            errors = [str(exc)]
        if attempt < attempts:
            cache_hit = False
    if errors or not items:
        raise GenerationError(errors or ["迭代生成失败"], last_raw)
    if use_cache and not cache_hit:
        _write_json(cache_path, {"text": raw, "model": model, "source": source,
                                 "created_at": _now(), "prompt_sha256": cache_path.stem})

    item = items[0]
    result = compiler.compile_spec(item, kind=kind, no_timestamp=True)
    base_dir = (Path(out_dir) / key) if out_dir else path.parent.parent
    base_candidate = path.parent.name
    base_candidate = base_candidate.split("-r", 1)[0]
    versions = [p for p in base_dir.glob(base_candidate + "-r*") if p.is_dir()]
    n = max([int(p.name.split("-r", 1)[1]) for p in versions if p.name.split("-r", 1)[1].isdigit()] or [1]) + 1
    new_dir = base_dir / ("%s-r%d" % (base_candidate, n))
    new_dir.mkdir(parents=True, exist_ok=True)
    _write_json(new_dir / "spec.json", item)
    (new_dir / ("%s.css" % key)).write_text(result["css"], encoding="utf-8")
    _write_json(new_dir / ("%s.registry.json" % key), result["registry"])
    return {
        "ok": True, "kind": kind, "key": key, "source": source, "model": model,
        "candidate": new_dir.name, "spec_path": str(new_dir / "spec.json"),
        "css": str(new_dir / ("%s.css" % key)), "css_bytes": len(result["css"].encode("utf-8")),
        "cache_hit": cache_hit, "comments": str(comments).strip(),
    }


def _write_compiled(out_dir, key, item, kind, candidate_name):
    result = compiler.compile_spec(item, kind=kind, no_timestamp=True)
    candidate_dir = Path(out_dir) / ("%s/%s" % (key, candidate_name))
    candidate_dir.mkdir(parents=True, exist_ok=True)
    _write_json(candidate_dir / "spec.json", item)
    (candidate_dir / ("%s.css" % key)).write_text(result["css"], encoding="utf-8")
    _write_json(candidate_dir / ("%s.registry.json" % key), result["registry"])
    return candidate_dir, result


def save_manual(spec_path, new_spec):
    """手动修改 Spec：不覆盖旧候选，写成新的 -eN 版本。"""
    path = Path(spec_path)
    old = json.loads(path.read_text(encoding="utf-8"))
    kind = old.get("kind")
    key = old.get("key")
    if kind not in ("layout", "theme") or not key:
        raise GenerationError(["候选 spec 缺少 kind/key"])
    if not isinstance(new_spec, dict) or str(new_spec.get("key")) != str(key):
        raise GenerationError(["手动编辑必须保持 key=%s" % key])
    errors = validate_candidates([new_spec], kind, expect=1)
    if errors:
        raise GenerationError(errors)
    key_dir = path.parents[1]
    base_candidate = path.parent.name
    versions = [p for p in key_dir.glob(base_candidate + "-e*") if p.is_dir()]
    n = max([int(p.name.split("-e", 1)[1]) for p in versions if p.name.split("-e", 1)[1].isdigit()] or [1]) + 1
    candidate_name = "%s-e%d" % (base_candidate, n)
    candidate_dir, result = _write_compiled(key_dir.parent, key, new_spec, kind, candidate_name)
    return {
        "ok": True, "kind": kind, "key": key, "candidate": candidate_name,
        "spec_path": str(candidate_dir / "spec.json"),
        "css": str(candidate_dir / ("%s.css" % key)),
        "css_bytes": len(result["css"].encode("utf-8")),
    }


def clone_published(kind, source_key, new_key, new_name, docs_dir, out_dir, builtin_dir=None):
    """从已发布 docs 或内置 Spec 复制一份新草稿；旧模板文件不动。"""
    if kind not in ("layout", "theme"):
        raise GenerationError(["kind 必须是 layout / theme"])
    builtin = Path(builtin_dir) if builtin_dir else Path(out_dir).parent / "builtin-specs" / kind
    sources = [
        ("docs", Path(docs_dir) / ("%s.json" % source_key)),
        ("builtin", builtin / ("%s.json" % source_key)),
    ]
    spec = None
    source = ""
    for label, path in sources:
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        candidate = data.get("spec") if label == "docs" else data
        if isinstance(candidate, dict):
            spec = json.loads(json.dumps(candidate, ensure_ascii=False))
            source = label
            break
    if spec is None:
        raise GenerationError(["没有可克隆的 Spec：%s（已发布 AI 模板与内置模板都没有）" % source_key])
    spec["key"] = new_key
    spec["name"] = new_name or spec.get("name") or new_key
    prefix = "基于内置模板 %s 维护的新版本" if source == "builtin" else "基于 %s 维护的新版本"
    spec["intent"] = "%s：%s" % (prefix % source_key, spec.get("intent", ""))[:120]
    errors = validate_candidates([spec], kind, expect=1)
    if errors:
        raise GenerationError(errors)
    candidate_dir, result = _write_compiled(out_dir, new_key, spec, kind, "candidate-1")
    return {
        "ok": True, "kind": kind, "source_key": source_key, "key": new_key,
        "candidate": "candidate-1", "spec_source": source,
        "spec_path": str(candidate_dir / "spec.json"),
        "css": str(candidate_dir / ("%s.css" % new_key)),
        "css_bytes": len(result["css"].encode("utf-8")),
    }
