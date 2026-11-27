#!/usr/bin/env python3
"""IDE 工作台后端：模型目录、AI 改 Spec、草稿预览。

安全边界：AI 只返回 Spec JSON，服务端做 schema 校验；不执行模型输出，
不自动批准，不写 assets/。自定义模型只用于本机请求，暂不落盘。
"""
from __future__ import annotations

import importlib.util
import json
import os
import urllib.parse
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
