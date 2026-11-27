#!/usr/bin/env python3
"""A4 草稿转正式：人工批准后原子发布；批准前不碰运行目录。"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

import compiler
import registry

ROOT = Path(__file__).resolve().parents[2]
DRAFTS = "tools/ai-template/drafts"
DOCS = "docs/templates"
REVIEWS = "tools/ai-template/reviews"
KEY_RE = re.compile(r"^[a-z0-9-]{3,24}$")
REASONS = ("同质化", "破版", "观感差", "不支持该场景")


class PublishError(RuntimeError):
    def __init__(self, code, message, details=None):
        self.code = code
        self.details = details or {}
        super().__init__(message)

    def as_dict(self):
        return {"ok": False, "code": self.code, "message": str(self), **self.details}


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S+08:00")


def _atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        if isinstance(content, bytes):
            tmp.write_bytes(content)
        else:
            tmp.write_text(content, encoding="utf-8")
        os.replace(str(tmp), str(path))
    finally:
        if tmp.exists():
            tmp.unlink()


def _transaction(files):
    """按顺序原子写；任一失败回滚已写文件与新建文件。"""
    backups = {}
    try:
        for path, content in files:
            path = Path(path)
            backups[path] = path.read_bytes() if path.exists() else None
            _atomic_write(path, content)
    except Exception:
        for path, old in backups.items():
            try:
                if old is None:
                    if path.exists():
                        path.unlink()
                else:
                    _atomic_write(path, old)
            except Exception:
                pass
        raise


def _review_path(root, key, suffix):
    day = time.strftime("%Y%m%d")
    base = Path(root) / REVIEWS / ("%s-%s%s.json" % (day, key, suffix))
    if not base.exists():
        return base
    for i in range(2, 20):
        candidate = base.with_name(base.stem + "-%d.json" % i)
        if not candidate.exists():
            return candidate
    return base


def _relative(root, path):
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve()))
    except ValueError:
        return str(path)


def _load_candidate(spec_path):
    path = Path(spec_path).resolve()
    if not path.exists():
        raise PublishError("CANDIDATE_MISSING", "找不到候选 spec")
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise PublishError("CANDIDATE_BAD_JSON", "候选 spec 不是合法 JSON:%s" % exc)
    return path, spec


def _metrics(path):
    metrics_path = path.parent / "metrics.json"
    if not metrics_path.exists():
        raise PublishError("APPROVE_GATES_MISSING", "候选没有 metrics.json，先跑 preview")
    try:
        data = json.loads(metrics_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise PublishError("APPROVE_GATES_BAD", "metrics.json 不合法:%s" % exc)
    if not data.get("ok"):
        failed = [g.get("code") for g in data.get("gates", []) if not g.get("ok")]
        raise PublishError("APPROVE_GATES_FAILED", "候选未过闸门", {"gates": failed})
    if data.get("visual") != "checked":
        raise PublishError("APPROVE_VISUAL_UNVERIFIED", "未跑 Chrome 截图，不能批准")
    return data


def approve_candidate(spec_path, reviewer, root=ROOT, note="", model="", prompt_id="generate-v1", rounds=1):
    if not str(reviewer or "").strip():
        raise PublishError("APPROVE_REVIEWER", "批准必须填写 reviewer")
    path, spec = _load_candidate(spec_path)
    kind = spec.get("kind")
    key = spec.get("key")
    if kind not in ("layout", "theme"):
        raise PublishError("APPROVE_KIND", "kind 必须是 layout/theme")
    if not KEY_RE.match(str(key or "")):
        raise PublishError("APPROVE_KEY", "key 非法")
    metrics_data = _metrics(path)
    if registry.entry(registry.load_published(root), kind, key):
        raise PublishError("PUBLISH_EXISTS", "key 已发布:%s" % key)
    try:
        compiled = compiler.compile_spec(spec, kind=kind, no_timestamp=True)
    except compiler.SpecError as exc:
        raise PublishError("PUBLISH_COMPILE", "编译失败", {"errors": exc.errors})
    css = compiled["css"]
    css_sha = hashlib.sha256(css.encode("utf-8")).hexdigest()
    css_rel = ("assets/layouts/%s.css" if kind == "layout" else "assets/themes/%s.css") % key
    docs_rel = "%s/%s.json" % (DOCS, key)
    docs_md_rel = "%s/%s.md" % (DOCS, key)
    review_path = _review_path(root, key, "")
    review_rel = _relative(root, review_path)
    at = _now()

    entry = dict(compiled["registry"])
    entry.update({
        "key": key, "label": spec.get("name", key), "source": "AI", "status": "published",
        "published_at": at, "spec": docs_rel, "review": review_rel,
        "archetype": spec.get("archetype", ""),
        "nav": bool(entry.get("nav")), "lead": bool(entry.get("lead")),
        "bands": bool(entry.get("bands")), "toc": bool(entry.get("toc")),
    })
    review = {
        "key": key, "kind": kind, "reviewer": str(reviewer).strip(),
        "decision": "approved", "at": at, "spec": _relative(root, path),
        "docs": docs_rel, "css": css_rel, "css_sha256": css_sha,
        "model": model or "", "prompt_id": prompt_id or "", "rounds": rounds,
        "candidates": len(list(path.parent.parent.glob("candidate-*"))),
        "note": str(note or "").strip(),
        "metrics": {
            "cssBytes": metrics_data.get("metrics", {}).get("cssBytes"),
            "shots": metrics_data.get("metrics", {}).get("shots"),
            "gates": [g.get("gate") for g in metrics_data.get("gates", []) if g.get("ok")],
        },
    }
    provenance = {
        "key": key, "kind": kind, "name": spec.get("name"), "intent": spec.get("intent"),
        "source": "AI", "status": "published", "published_at": at,
        "reviewer": review["reviewer"], "model": review["model"],
        "prompt_id": review["prompt_id"], "rounds": rounds,
        "css": css_rel, "css_sha256": css_sha, "review": review_rel,
        "spec": spec, "metrics": metrics_data.get("metrics", {}),
    }
    md_lines = [
        "# %s · %s" % (spec.get("name", key), key),
        "",
        "- 类型：%s" % ("版式" if kind == "layout" else "主题"),
        "- 来源：AI / %s" % (model or "unknown"),
        "- 审批人：%s" % review["reviewer"],
        "- 批准时间：%s" % at,
        "- CSS：`%s`（%s bytes，sha256 `%s`）" % (css_rel, len(css.encode("utf-8")), css_sha[:16]),
        "- 候选：`%s`" % review["spec"],
        "",
        "## 设计意图",
        "",
        str(spec.get("intent") or ""),
        "",
        "## 理由",
        "",
    ]
    md_lines.extend("- %s" % item for item in spec.get("rationale", []))
    md_lines.extend(["", "## 闸门", "", "G1–G6 全部通过；截图 %s 张。" % review["metrics"].get("shots")])
    doc_json = json.dumps(provenance, ensure_ascii=False, indent=2) + "\n"
    review_json = json.dumps(review, ensure_ascii=False, indent=2) + "\n"
    md = "\n".join(md_lines).rstrip() + "\n"

    published_path = registry.published_path(root)
    published = registry.load_published(root)
    published.setdefault("layouts" if kind == "layout" else "themes", {})[key] = entry
    published_text = json.dumps(published, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        js_path, js_text, marker = registry.js_marker(kind, root)
        js_new = registry.insert_js_entry(kind, key, entry, root)
    except ValueError as exc:
        raise PublishError("PUBLISH_REGISTRY", str(exc))
    files = [
        (Path(root) / css_rel, css),
        (Path(root) / docs_rel, doc_json),
        (Path(root) / docs_md_rel, md),
        (review_path, review_json),
        (js_path, js_new),
        (published_path, published_text),
    ]
    try:
        _transaction(files)
    except Exception as exc:
        raise PublishError("PUBLISH_FAILED", "发布失败，已回滚:%s" % exc)
    return {"ok": True, "key": key, "kind": kind, "css": css_rel, "docs": docs_rel,
            "docsMd": docs_md_rel, "review": review_rel, "cssSha256": css_sha,
            "bytes": len(css.encode("utf-8"))}


def reject_candidate(spec_path, reviewer, reason, note="", root=ROOT):
    if not str(reviewer or "").strip():
        raise PublishError("REJECT_REVIEWER", "驳回必须填写 reviewer")
    if reason not in REASONS:
        raise PublishError("REJECT_REASON", "驳回原因必须是 %s" % " / ".join(REASONS))
    path, spec = _load_candidate(spec_path)
    key = str(spec.get("key") or "unknown")
    review_path = _review_path(root, key, "-reject")
    record = {
        "key": key, "kind": spec.get("kind"), "reviewer": str(reviewer).strip(),
        "decision": "rejected", "reason": reason, "note": str(note or "").strip(),
        "at": _now(), "spec": _relative(root, path),
    }
    _atomic_write(review_path, json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    return {"ok": True, "key": key, "review": _relative(root, review_path)}


def record_revision(spec_path, comments, reviewer="", root=ROOT):
    path, spec = _load_candidate(spec_path)
    key = str(spec.get("key") or "unknown")
    if not str(comments or "").strip():
        raise PublishError("REVISE_COMMENTS", "迭代必须填写意见")
    existing = sorted((Path(root) / REVIEWS).glob("*-%s-revise-*.json" % key))
    round_no = len(existing) + 1
    if round_no > 2:
        raise PublishError("REVISE_LIMIT", "该设计已迭代 2 轮，转人工设计")
    review_path = Path(root) / REVIEWS / ("%s-%s-revise-%d.json" % (time.strftime("%Y%m%d"), key, round_no))
    record = {
        "key": key, "kind": spec.get("kind"), "reviewer": str(reviewer or "").strip(),
        "decision": "revise", "round": round_no, "comments": str(comments).strip(),
        "at": _now(), "spec": _relative(root, path),
    }
    _atomic_write(review_path, json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    return {"ok": True, "key": key, "round": round_no, "review": _relative(root, review_path)}
