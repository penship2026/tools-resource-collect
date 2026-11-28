#!/usr/bin/env python3
"""IDE 工作台后端：模型目录、AI 改 Spec、草稿预览。

安全边界：AI 只返回 Spec JSON，服务端做 schema 校验；不执行模型输出，
不自动批准，不写 assets/。自定义模型只用于本机请求，暂不落盘。
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import urllib.parse
from datetime import datetime
from pathlib import Path

import compiler
import generate
import preview
from adapters import openai_compat


def _template_generate():
    """避免测试或宿主先导入 collector/generate 造成同名模块遮蔽。"""
    if hasattr(generate, "read_system") and hasattr(generate, "parse_candidates"):
        return generate
    path = Path(__file__).with_name("generate.py")
    spec = importlib.util.spec_from_file_location("jiye_template_generate", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class StudioError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)

    def as_dict(self):
        return {"ok": False, "code": self.code, "message": self.message}


PAGE_DEFS = (
    {"id": "home", "label": "首页", "html": "index.html", "css": "assets/pages/index.css",
     "preview": "/repo/index.html", "needs_id": False},
    {"id": "series", "label": "集合页", "html": "series.html", "css": "assets/pages/series.css",
     "preview": "/repo/series.html", "needs_id": True},
    {"id": "list", "label": "列表页", "html": "list.html", "css": "assets/pages/list.css",
     "preview": "/repo/list.html", "needs_id": True},
    {"id": "single", "label": "详情页", "html": "single.html", "css": "assets/pages/single.css",
     "preview": "/repo/single.html", "needs_id": True},
)
PAGE_PATHS = {x["html"] for x in PAGE_DEFS} | {x["css"] for x in PAGE_DEFS}


def _first_unit_id(root):
    index = Path(root) / "assets" / "data" / "index.js"
    if not index.exists():
        return ""
    text = index.read_text(encoding="utf-8")
    match = re.search(r"window\.COLLECTION_INDEX\s*=\s*(\[[\s\S]*?\])\s*;", text)
    if not match:
        return ""
    try:
        items = json.loads(match.group(1))
    except ValueError:
        return ""
    return str(items[0].get("id") or "") if items else ""


def page_catalog(root=None):
    """四个页面及各自 HTML/CSS 文件的编辑入口。"""
    unit = _first_unit_id(root) if root else ""
    items = []
    for page in PAGE_DEFS:
        preview = page["preview"]
        if page["needs_id"] and unit:
            preview += ("&" if "?" in preview else "?") + "id=" + urllib.parse.quote(unit)
        items.append({
            "id": page["id"], "label": page["label"],
            "html": page["html"], "css": page["css"], "preview": preview,
        })
    return {"ok": True, "items": items}


def _page_path(root, path):
    path = str(path or "").replace("\\", "/").lstrip("/")
    if path not in PAGE_PATHS:
        raise StudioError("PAGE_PATH", "只能编辑首页、集合页、列表页、详情页及其页面 CSS")
    return path


def save_page(root, path, content):
    """保存页面文件；先备份旧文件，再原子替换。"""
    rel = _page_path(root, path)
    if not isinstance(content, str) or not content.strip():
        raise StudioError("PAGE_EMPTY", "文件内容为空")
    if len(content.encode("utf-8")) > 512 * 1024:
        raise StudioError("PAGE_TOO_LARGE", "单个页面文件不能超过 512KB")
    if rel.endswith(".html") and ("<html" not in content.lower() or "</html>" not in content.lower()):
        raise StudioError("PAGE_HTML", "HTML 必须保留 <html> 完整文档结构")
    target = Path(root) / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = Path(root) / "backups" / "pages" / datetime.now().strftime("%Y%m%d-%H%M%S-%f") / Path(rel).name
    backup.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        backup.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(target)
    return {"ok": True, "path": rel, "bytes": len(content.encode("utf-8")),
            "backup": backup.relative_to(Path(root)).as_posix(), "message": "页面已保存，旧文件已备份"}


def edit_page(root, path, content, instruction, model_id="", custom=None, adapter=None):
    """让模型改一个完整页面文件；不落盘、不部署。"""
    rel = _page_path(root, path)
    if not isinstance(content, str) or not content.strip():
        raise StudioError("PAGE_EMPTY", "当前文件为空")
    instruction = str(instruction or "").strip()
    if not instruction:
        raise StudioError("EDIT_EMPTY", "先写下要改什么")
    if adapter is None:
        cfg = resolve_model(model_id, custom, root)
        adapter = openai_compat.OpenAICompat(cfg["base_url"], cfg["api_key"], cfg["model"], cfg.get("timeout", 180))
    language = "CSS" if rel.endswith(".css") else "HTML"
    system = (
        "你是集页静态站的页面编辑助手。只输出修改后的完整%s文件正文，"
        "不要解释、不要 markdown 代码块、不要 diff。\n"
        "必须保留页面现有的数据加载方式、DOM id、脚本依赖与响应式行为；"
        "不引入外部 CDN、外部字体、远程接口或构建步骤；不写后端与部署配置。\n"
        "HTML 必须保留 <!DOCTYPE html> 与 <html>...</html> 完整结构；"
        "CSS 必须保留现有选择器的语义，不写 @import。" % language
    )
    user = "当前文件：%s\n\n```%s\n%s\n```\n\n修改要求：%s" % (
        rel, language.lower(), content, instruction)
    try:
        raw = adapter.complete(system, user, kind="page")
    except openai_compat.AdapterError as exc:
        raise StudioError("MODEL_FAILED", str(exc))
    text = str(raw or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    if not text:
        raise StudioError("MODEL_EMPTY", "模型没有返回文件内容")
    if len(text.encode("utf-8")) > 512 * 1024:
        raise StudioError("MODEL_TOO_LARGE", "模型返回内容超过 512KB")
    if rel.endswith(".html") and ("<html" not in text.lower() or "</html>" not in text.lower()):
        raise StudioError("MODEL_HTML", "模型返回的不是完整 HTML 文档")
    if rel.endswith(".css") and text.count("{") != text.count("}"):
        raise StudioError("MODEL_CSS", "模型返回的 CSS 大括号不完整，可能被截断")
    return {"ok": True, "path": rel, "content": text, "model": getattr(adapter, "model", "") or model_id,
            "message": "AI 已返回页面修改版；尚未保存，确认后再写入。"}


def _env_int(name, default):
    try:
        return int(os.environ.get(name) or default)
    except (TypeError, ValueError):
        return default


def _current_config():
    openai_compat.load_env_file()
    base = os.environ.get("AI_BASE_URL", "").strip()
    key = os.environ.get("AI_API_KEY", "").strip()
    model = os.environ.get("AI_MODEL", "").strip()
    if not (base and key and model):
        return None
    return {
        "id": "env",
        "label": "%s · 本机 .env" % model,
        "base_url": base,
        "api_key": key,
        "model": model,
        "timeout": _env_int("AI_TIMEOUT", 180),
        "provider": "env",
    }


def _preset_models():
    models = []
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    models.append({
        "id": "openrouter/free",
        "label": "OpenRouter · ERNIE 5.5 Flash Free",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": openrouter_key,
        "model": "baidu/ernie-5.5-flash-preview:free",
        "timeout": 120,
        "provider": "openrouter",
        "available": bool(openrouter_key),
    })
    models.append({
        "id": "ollama/llama3.2",
        "label": "Ollama 本机 · llama3.2",
        "base_url": "http://127.0.0.1:11434/v1",
        "api_key": "ollama-local",
        "model": "llama3.2",
        "timeout": 300,
        "provider": "ollama",
        "available": True,
    })
    return models


def _custom_models_from_env():
    raw = os.environ.get("AI_MODELS", "").strip()
    if not raw:
        return []
    try:
        items = json.loads(raw)
    except ValueError:
        return []
    if not isinstance(items, list):
        return []
    out = []
    for i, item in enumerate(items, 1):
        if not isinstance(item, dict):
            continue
        base = str(item.get("base_url") or "").strip()
        model = str(item.get("model") or "").strip()
        if not base or not model:
            continue
        out.append({
            "id": str(item.get("id") or "custom-%d" % i),
            "label": str(item.get("label") or item.get("name") or model),
            "base_url": base,
            "api_key": str(item.get("api_key") or ""),
            "model": model,
            "timeout": item.get("timeout") or 180,
            "provider": "custom",
            "available": True,
        })
    return out


def model_catalog(root=None):
    """返回可切换模型；不返回任何 api_key。"""
    current = _current_config()
    items = []
    if current:
        items.append(current)
    items.extend(_custom_models_from_env())
    items.extend(_preset_models())
    seen = set()
    out = []
    for item in items:
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        out.append({k: v for k, v in item.items() if k != "api_key"})
    return {
        "ok": True,
        "default": "env" if current else (out[0]["id"] if out else ""),
        "items": out,
    }


def resolve_model(model_id="", custom=None, root=None):
    """把前端选择解析成适配器配置；custom 仅本次请求使用。"""
    if isinstance(custom, dict) and custom.get("base_url") and custom.get("model"):
        base = str(custom["base_url"]).strip()
        if not base.startswith(("http://", "https://")):
            raise StudioError("MODEL_URL", "自定义模型地址必须是 http(s)")
        return {
            "id": "custom",
            "label": str(custom.get("label") or custom.get("model")),
            "base_url": base.rstrip("/"),
            "api_key": str(custom.get("api_key") or ""),
            "model": str(custom["model"]).strip(),
            "timeout": custom.get("timeout") or 180,
            "provider": "custom",
        }
    current = _current_config()
    all_items = (_custom_models_from_env() + _preset_models())
    if current:
        all_items.insert(0, current)
    wanted = str(model_id or "").strip() or ("env" if current else "")
    for item in all_items:
        if item["id"] == wanted:
            if not item.get("api_key") and item.get("provider") != "ollama":
                raise StudioError("MODEL_KEY", "该模型未配置 API Key")
            return item
    raise StudioError("MODEL_NOT_FOUND", "找不到模型：%s" % wanted)


def _edit_prompt(spec, instruction):
    template = (Path(__file__).resolve().parent / "prompts" / "edit.md").read_text(encoding="utf-8")
    return (template
            + "\n\n当前 Spec：\n```json\n"
            + json.dumps(spec, ensure_ascii=False, indent=2)
            + "\n```\n\n修改要求：\n" + str(instruction or "").strip())


def edit_spec(spec, kind, instruction, model_id="", custom=None, adapter=None, root=None):
    """让模型改当前 Spec；返回新 Spec，不保存、不批准。"""
    if not isinstance(spec, dict):
        raise StudioError("SPEC_OBJECT", "当前源码不是对象")
    if kind not in ("layout", "theme"):
        raise StudioError("SPEC_KIND", "未知类型")
    if spec.get("kind") != kind:
        raise StudioError("SPEC_KIND", "Spec kind 与当前类型不一致")
    errors = compiler.validate_layout_spec(spec) if kind == "layout" else compiler.validate_theme_spec(spec)
    if errors:
        raise StudioError("SPEC_INVALID", "当前 Spec 未通过校验：" + "; ".join(errors[:5]))
    instruction = str(instruction or "").strip()
    if not instruction:
        raise StudioError("EDIT_EMPTY", "先写下要改什么")
    if adapter is None:
        cfg = resolve_model(model_id, custom, root)
        adapter = openai_compat.OpenAICompat(
            cfg["base_url"], cfg["api_key"], cfg["model"], cfg.get("timeout", 180)
        )
    gen = _template_generate()
    system = gen.read_system(kind, 1)
    user = _edit_prompt(spec, instruction)
    try:
        raw = adapter.complete(system, user, kind=kind)
    except openai_compat.AdapterError as exc:
        raise StudioError("MODEL_FAILED", str(exc))
    try:
        items = gen.parse_candidates(raw)
    except gen.CandidateError as exc:
        raise StudioError("MODEL_JSON", str(exc))
    if not items or not isinstance(items[0], dict):
        raise StudioError("MODEL_JSON", "模型没有返回 Spec 对象")
    new_spec = items[0]
    if new_spec.get("kind") != kind:
        raise StudioError("EDIT_KIND", "模型改了 kind，已拒绝")
    if new_spec.get("key") != spec.get("key"):
        raise StudioError("EDIT_KEY", "模型改了 key，已拒绝")
    errors = compiler.validate_layout_spec(new_spec) if kind == "layout" else compiler.validate_theme_spec(new_spec)
    if errors:
        raise StudioError("MODEL_SPEC_INVALID", "模型返回的 Spec 不合法：" + "; ".join(errors[:5]))
    return {
        "ok": True,
        "spec": new_spec,
        "model": getattr(adapter, "model", "") or model_id,
        "message": "AI 已给出修改版；尚未保存，确认后保存为新版本。",
    }


def preview_draft(spec, kind, root):
    """把编辑中的 Spec 编译成临时预览，不进入候选列表。"""
    if not isinstance(spec, dict):
        raise StudioError("SPEC_OBJECT", "当前源码不是对象")
    errors = compiler.validate_layout_spec(spec) if kind == "layout" else compiler.validate_theme_spec(spec)
    if errors:
        raise StudioError("SPEC_INVALID", "; ".join(errors[:6]))
    key = spec.get("key", "")
    if not key:
        raise StudioError("SPEC_KEY", "Spec 缺少 key")
    out = Path(root) / "tools" / "ai-template" / "drafts" / key / "studio-preview"
    out.mkdir(parents=True, exist_ok=True)
    (out / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    result = compiler.compile_spec(spec, kind=kind, no_timestamp=True)
    css_path = out / ("%s.css" % key)
    css_path.write_text(result["css"], encoding="utf-8")
    (out / ("%s.registry.json" % key)).write_text(
        json.dumps(result["registry"], ensure_ascii=False, indent=2), encoding="utf-8")
    preview.build_preview(spec, kind, css_path, out / "preview" / "index.html")
    return {
        "ok": True,
        "kind": kind,
        "key": key,
        "candidate": "studio-preview",
        "preview": "/preview/%s/%s/studio-preview/" % (kind, key),
        "cssBytes": len(result["css"].encode("utf-8")),
        "message": "草稿预览已更新（未保存）",
    }
