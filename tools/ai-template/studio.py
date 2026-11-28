#!/usr/bin/env python3
"""IDE 工作台后端：模型目录、AI 改 Spec、草稿预览。

安全边界：AI 只返回 Spec JSON，服务端做 schema 校验；不执行模型输出，
不自动批准，不写 assets/。自定义模型只用于本机请求，暂不落盘。
"""
from __future__ import annotations

import importlib.util
import difflib
import json
import os
import re
import urllib.parse
from datetime import datetime
from html.parser import HTMLParser
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
    def __init__(self, code, message, details=None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def as_dict(self):
        data = {"ok": False, "code": self.code, "message": self.message}
        if self.details:
            data.update(self.details)
        return data


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
PAGE_HISTORY_LIMIT = 20
PAGE_HISTORY_RE = re.compile(r"^\d{8}-\d{6}-\d{6}$")


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


_HTML_VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}
_HTML_OPTIONAL = {
    "li", "p", "td", "th", "tr", "thead", "tbody", "tfoot", "option",
    "dt", "dd", "colgroup", "caption",
}
_HTML_AUTO_CLOSE = {
    "li": {"li"},
    "p": {"p"},
    "td": {"td", "th"},
    "th": {"td", "th"},
    "tr": {"td", "th", "tr"},
    "thead": {"thead", "tbody", "tfoot"},
    "tbody": {"thead", "tbody", "tfoot"},
    "tfoot": {"thead", "tbody", "tfoot"},
    "option": {"option"},
    "dt": {"dt", "dd"},
    "dd": {"dt", "dd"},
}
_HTML_REF_ATTR = {
    "link": "href", "script": "src", "img": "src",
    "source": "src", "iframe": "src", "video": "src", "audio": "src",
}


def _issue(code, message, line=None, column=None):
    item = {"code": code, "message": message}
    if line:
        item["line"] = int(line)
    if column:
        item["column"] = int(column)
    return item


def _local_ref(value):
    """把页面里的静态资源引用归一化为站内相对路径；外部/动态引用返回空串。"""
    value = str(value or "").strip()
    if not value:
        return ""
    lower = value.lower()
    if lower.startswith(("#", "http://", "https://", "//", "data:", "mailto:", "javascript:", "tel:")):
        return ""
    if "${" in value or "{{" in value or "' +" in value or '" +' in value:
        return ""
    value = value.split("#", 1)[0].split("?", 1)[0].strip()
    if not value:
        return ""
    if value.startswith("/repo/"):
        value = value[len("/repo/"):]
    elif value.startswith("/"):
        value = value.lstrip("/")
    while value.startswith("./"):
        value = value[2:]
    return value


class _PageHtmlValidator(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.stack = []
        self.errors = []
        self.warnings = []
        self.counts = {}
        self.ids = {}
        self.refs = []
        self.css_links = []
        self.doctype = 0
        self.html_lang = ""
        self._line_count = 1

    def _at(self, code, message, column=None, warning=False):
        line = self.getpos()[0]
        self._line_count = max(self._line_count, line)
        (self.warnings if warning else self.errors).append(
            _issue(code, message, line, column if column is not None else self.getpos()[1] + 1)
        )

    def _open(self, tag, attrs, self_closing=False):
        tag = tag.lower()
        attrs_map = {str(k).lower(): (v if v is not None else "") for k, v in attrs}
        if tag in ("html", "head", "body"):
            self.counts[tag] = self.counts.get(tag, 0) + 1
            if self.counts[tag] > 1:
                self._at("PAGE_HTML_STRUCTURE", "<%s> 只能出现一次，当前重复" % tag)
        if tag == "html":
            self.html_lang = attrs_map.get("lang", "")
        if tag == "link" and "stylesheet" in attrs_map.get("rel", "").lower():
            href = _local_ref(attrs_map.get("href"))
            if href:
                self.css_links.append(href)
        if tag in _HTML_REF_ATTR:
            attr = _HTML_REF_ATTR[tag]
            ref = _local_ref(attrs_map.get(attr))
            if ref:
                self.refs.append((tag, ref, self.getpos()[0]))
        ident = attrs_map.get("id")
        if ident:
            if ident in self.ids:
                self._at("PAGE_HTML_DUP_ID", "id 重复：%s（首次在第 %d 行）" % (ident, self.ids[ident]), warning=True)
            else:
                self.ids[ident] = self.getpos()[0]
        if tag in _HTML_VOID:
            return
        if self_closing:
            self._at("PAGE_HTML_SELF_CLOSE", "非空标签 <%s/> 使用了自闭合写法" % tag, warning=True)
            return
        while self.stack and self.stack[-1][0] in _HTML_AUTO_CLOSE.get(tag, set()):
            self.stack.pop()
        self.stack.append((tag, self.getpos()[0]))

    def handle_starttag(self, tag, attrs):
        self._open(tag, attrs, False)

    def handle_startendtag(self, tag, attrs):
        self._open(tag, attrs, True)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _HTML_VOID:
            self._at("PAGE_HTML_UNEXPECTED", "空标签 </%s> 不需要闭合" % tag, warning=True)
            return
        idx = None
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                idx = i
                break
        if idx is None:
            self._at("PAGE_HTML_UNEXPECTED", "意外的结束标签 </%s>，没有对应的开始标签" % tag)
            return
        above = self.stack[idx + 1:]
        bad = [x for x in above if x[0] not in _HTML_OPTIONAL]
        if bad:
            names = " / ".join("<%s> 第 %d 行" % (x[0], x[1]) for x in bad[:3])
            self._at("PAGE_HTML_UNCLOSED", "闭合 </%s> 前还有未闭合标签：%s" % (tag, names))
        self.stack = self.stack[:idx]

    def handle_decl(self, decl):
        if decl.strip().lower().startswith("doctype"):
            self.doctype += 1

    def finish(self):
        if self.doctype == 0:
            self.errors.append(_issue("PAGE_HTML_DOCTYPE", "缺少 <!DOCTYPE html> 文档声明", 1))
        elif self.doctype > 1:
            self.warnings.append(_issue("PAGE_HTML_DOCTYPE", "存在多个 DOCTYPE 声明", 1))
        for tag in ("html", "head", "body"):
            if self.counts.get(tag, 0) == 0:
                self.errors.append(_issue("PAGE_HTML_STRUCTURE", "缺少 <%s> 结构" % tag, 1))
        if not self.html_lang:
            self.warnings.append(_issue("PAGE_HTML_LANG", "<html> 缺少 lang 属性", 1))
        for tag, line in self.stack:
            if tag in _HTML_OPTIONAL:
                self.warnings.append(_issue("PAGE_HTML_UNCLOSED", "可选标签 <%s> 未显式闭合" % tag, line))
            else:
                self.errors.append(_issue("PAGE_HTML_UNCLOSED", "标签 <%s> 没有闭合" % tag, line))
        return self.errors, self.warnings


def _scan_css(text):
    errors = []
    warnings = []
    braces = []
    parens = []
    line = 1
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\n":
            line += 1
            i += 1
            continue
        if text.startswith("/*", i):
            start = line
            end = text.find("*/", i + 2)
            if end < 0:
                errors.append(_issue("PAGE_CSS_COMMENT", "块注释没有闭合（从第 %d 行开始）" % start, start))
                break
            line += text[i:end + 2].count("\n")
            i = end + 2
            continue
        if ch in "\"'":
            quote = ch
            start = line
            i += 1
            closed = False
            while i < n:
                c = text[i]
                if c == "\\":
                    i += 2
                    continue
                if c == quote:
                    i += 1
                    closed = True
                    break
                if c == "\n":
                    errors.append(_issue("PAGE_CSS_STRING", "字符串缺少结束引号（从第 %d 行开始）" % start, start))
                    line += 1
                    i += 1
                    break
                i += 1
            if not closed and i >= n:
                errors.append(_issue("PAGE_CSS_STRING", "字符串缺少结束引号（从第 %d 行开始）" % start, start))
            continue
        if ch == "{":
            braces.append(line)
        elif ch == "}":
            if braces:
                braces.pop()
            else:
                errors.append(_issue("PAGE_CSS_BRACE", "多余的右花括号 }", line))
        elif ch == "(":
            parens.append(line)
        elif ch == ")":
            if parens:
                parens.pop()
            else:
                errors.append(_issue("PAGE_CSS_PAREN", "多余的右括号 )", line))
        i += 1
    for start in braces:
        errors.append(_issue("PAGE_CSS_BRACE", "花括号没有闭合（从第 %d 行开始）" % start, start))
    if parens:
        for start in parens:
            errors.append(_issue("PAGE_CSS_PAREN", "括号没有闭合（从第 %d 行开始）" % start, start))
    if re.search(r"</?(?:html|head|body|style|script)\b", text, re.I):
        errors.append(_issue("PAGE_CSS_HTML", "CSS 中混入了 HTML 标签，请检查文件拼接", 1))
    if not text.strip():
        errors.append(_issue("PAGE_EMPTY", "文件内容为空", 1))
    return errors, warnings


def validate_page(root, path, content):
    """保存前校验：HTML/CSS 语法、结构、资源拼接与引用完整性。"""
    rel = _page_path(root, path)
    content = content if isinstance(content, str) else ""
    errors = []
    warnings = []
    if not content.strip():
        errors.append(_issue("PAGE_EMPTY", "文件内容为空", 1))
    size = len(content.encode("utf-8"))
    if size > 512 * 1024:
        errors.append(_issue("PAGE_TOO_LARGE", "单个页面文件不能超过 512KB", 1))
    if rel.endswith(".html"):
        parser = _PageHtmlValidator()
        try:
            parser.feed(content)
            parser.close()
            parser.finish()
        except Exception as exc:
            errors.append(_issue("PAGE_HTML_PARSE", "HTML 解析失败：%s" % exc, 1))
        errors.extend(parser.errors)
        warnings.extend(parser.warnings)
        page = next((x for x in PAGE_DEFS if x["html"] == rel), None)
        if page:
            expected = page["css"]
            if expected not in parser.css_links:
                errors.append(_issue(
                    "PAGE_HTML_CSS", "缺少页面样式引用：%s" % expected, 1,
                ))
            for href in parser.css_links:
                if href in PAGE_PATHS and href != expected:
                    warnings.append(_issue(
                        "PAGE_HTML_CSS_MISMATCH", "引用了非当前页面 CSS：%s" % href, 1,
                    ))
        for tag, ref, line in parser.refs:
            target = Path(root) / ref
            if not target.exists():
                errors.append(_issue(
                    "PAGE_HTML_REF", "<%s> 引用的文件不存在：%s" % (tag, ref), line,
                ))
    else:
        css_errors, css_warnings = _scan_css(content)
        errors.extend(css_errors)
        warnings.extend(css_warnings)
    return {
        "ok": not errors,
        "path": rel,
        "kind": "css" if rel.endswith(".css") else "html",
        "bytes": size,
        "errors": errors,
        "warnings": warnings,
        "stats": {"errors": len(errors), "warnings": len(warnings)},
    }


def _version_label(root, rel, version):
    if version == "current":
        return "当前版本"
    items = _page_history_items(root, rel)
    return next((x["label"] for x in items if x["version"] == version), version)


def _read_version(root, rel, version):
    if version == "current":
        target = Path(root) / rel
        if not target.exists():
            raise StudioError("PAGE_NOT_FOUND", "当前页面文件不存在")
        content = target.read_text(encoding="utf-8")
        stat = target.stat()
        return {
            "version": "current", "label": "当前版本",
            "iso": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%m-%d %H:%M:%S"),
            "bytes": len(content.encode("utf-8")), "content": content,
        }
    version = str(version or "")
    if not PAGE_HISTORY_RE.match(version):
        raise StudioError("HISTORY_VERSION", "历史版本标识不合法")
    target = _history_file(root, rel, version)
    if target is None:
        raise StudioError("HISTORY_NOT_FOUND", "该历史版本不存在")
    content = target.read_text(encoding="utf-8")
    items = _page_history_items(root, rel)
    meta = next((x for x in items if x["version"] == version), {})
    return {
        "version": version, "label": meta.get("label", version),
        "iso": meta.get("iso", ""), "mtime": meta.get("label", version),
        "bytes": len(content.encode("utf-8")), "content": content,
    }


def _diff_payload(path, kind, left_item, right_item):
    a = left_item["content"].splitlines()
    b = right_item["content"].splitlines()
    lines = list(difflib.unified_diff(
        a, b, fromfile="%s · %s" % (path, left_item["label"]),
        tofile="%s · %s" % (path, right_item["label"]),
        lineterm="", n=3,
    ))
    added = sum(1 for x in lines if x.startswith("+") and not x.startswith("+++"))
    removed = sum(1 for x in lines if x.startswith("-") and not x.startswith("---"))
    truncated = len(lines) > 20000
    return {
        "ok": True, "path": path, "kind": kind,
        "left": {k: left_item.get(k, "") for k in ("version", "label", "mtime", "bytes")},
        "right": {k: right_item.get(k, "") for k in ("version", "label", "mtime", "bytes")},
        "lines": lines[:20000], "truncated": truncated,
        "stats": {"added": added, "removed": removed},
    }


def diff_page_history(root, path, left, right):
    rel = _page_path(root, path)
    left = str(left or "")
    right = str(right or "")
    if left == right:
        raise StudioError("DIFF_SAME", "请选择两个不同的版本进行对比")
    left_item = _read_version(root, rel, left)
    right_item = _read_version(root, rel, right)
    return _diff_payload(rel, "css" if rel.endswith(".css") else "html", left_item, right_item)


def _history_file(root, rel, version):
    base = Path(root) / "backups" / "pages" / version
    candidates = (base / rel, base / Path(rel).name)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _page_history_items(root, rel):
    hist = Path(root) / "backups" / "pages"
    if not hist.is_dir():
        return []
    items = []
    for version_dir in hist.iterdir():
        if not version_dir.is_dir() or not PAGE_HISTORY_RE.match(version_dir.name):
            continue
        target = _history_file(root, rel, version_dir.name)
        if target is None:
            continue
        try:
            stamp = datetime.strptime(version_dir.name, "%Y%m%d-%H%M%S-%f")
        except ValueError:
            continue
        items.append({
            "version": version_dir.name,
            "label": stamp.strftime("%m-%d %H:%M:%S"),
            "iso": stamp.isoformat(timespec="seconds"),
            "bytes": target.stat().st_size,
            "kind": "css" if rel.endswith(".css") else "html",
            "path": rel,
            "_file": target,
        })
    items.sort(key=lambda item: item["version"], reverse=True)
    return items


def _prune_page_history(root, rel, limit=PAGE_HISTORY_LIMIT):
    items = _page_history_items(root, rel)
    hist = Path(root) / "backups" / "pages"
    for item in items[limit:]:
        target = item["_file"]
        try:
            target.unlink()
        except OSError:
            continue
        parent = target.parent
        while parent != hist and parent.is_dir():
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
    return len(items[:limit])


def save_page(root, path, content):
    """保存页面文件；先做语法/拼接校验，再备份旧文件并原子替换，历史最多保留 20 个。"""
    rel = _page_path(root, path)
    report = validate_page(root, rel, content)
    if not report["ok"]:
        messages = [x["message"] for x in report["errors"][:3]]
        raise StudioError(
            "PAGE_VALIDATE",
            "页面校验未通过：" + "；".join(messages),
            {"errors": report["errors"], "warnings": report["warnings"]},
        )
    content = content if isinstance(content, str) else ""
    target = Path(root) / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    backup_dir = Path(root) / "backups" / "pages" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = backup_dir / rel
    backup_rel = ""
    if target.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
        backup_rel = backup.relative_to(Path(root)).as_posix()
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(target)
    history_count = _prune_page_history(root, rel)
    return {"ok": True, "path": rel, "bytes": len(content.encode("utf-8")),
            "backup": backup_rel, "history_count": history_count,
            "history_limit": PAGE_HISTORY_LIMIT,
            "message": "页面已保存，旧文件已进入历史版本"}


def list_page_history(root, path, limit=PAGE_HISTORY_LIMIT):
    rel = _page_path(root, path)
    limit = max(1, min(int(limit or PAGE_HISTORY_LIMIT), PAGE_HISTORY_LIMIT))
    items = _page_history_items(root, rel)
    clean = [{k: v for k, v in item.items() if not k.startswith("_")} for item in items[:limit]]
    for item in clean:
        item["current"] = False
        item["mtime"] = item.get("label", "")
    target = Path(root) / rel
    current = None
    if target.exists():
        stat = target.stat()
        current = {
            "version": "current", "label": "当前版本", "current": True,
            "iso": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%m-%d %H:%M:%S"),
            "bytes": stat.st_size,
            "kind": "css" if rel.endswith(".css") else "html", "path": rel,
        }
    result_items = ([current] if current else []) + clean
    return {"ok": True, "path": rel, "kind": "css" if rel.endswith(".css") else "html",
            "limit": limit, "max": PAGE_HISTORY_LIMIT, "history_count": len(clean),
            "current": current, "items": result_items}


def read_page_history(root, path, version):
    rel = _page_path(root, path)
    item = _read_version(root, rel, version)
    item["kind"] = "css" if rel.endswith(".css") else "html"
    return {"ok": True, "path": rel, "type": "page", **item}


def _design_spec_path(root, path):
    raw = str(path or "")
    spec_path = (Path(root) / raw).resolve()
    drafts = (Path(root) / "tools" / "ai-template" / "drafts").resolve()
    if spec_path.name != "spec.json" or drafts not in spec_path.parents:
        raise StudioError("DESIGN_PATH", "只能读取 drafts 下的候选 spec.json")
    if not spec_path.is_file():
        raise StudioError("DESIGN_NOT_FOUND", "当前候选 spec.json 不存在")
    return spec_path


def _design_version(root, path, version):
    spec_path = _design_spec_path(root, path)
    key_dir = spec_path.parent.parent
    current_dir = spec_path.parent
    if version == "current":
        target_dir = current_dir
    else:
        version = str(version or "")
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*$", version) or version == "studio-preview":
            raise StudioError("DESIGN_VERSION", "候选版本标识不合法")
        target_dir = key_dir / version
        if not (target_dir / "spec.json").is_file():
            raise StudioError("DESIGN_NOT_FOUND", "该候选版本不存在")
    target = target_dir / "spec.json"
    content = target.read_text(encoding="utf-8")
    spec = json.loads(content)
    stat = target.stat()
    return {
        "version": target_dir.name, "candidate": target_dir.name,
        "label": target_dir.name, "iso": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%m-%d %H:%M:%S"),
        "bytes": len(content.encode("utf-8")), "content": content,
        "kind": spec.get("kind") or "", "key": spec.get("key") or "",
    }


def list_design_history(root, path):
    spec_path = _design_spec_path(root, path)
    key_dir = spec_path.parent.parent
    current_dir = spec_path.parent.name
    items = []
    for folder in key_dir.iterdir():
        spec_file = folder / "spec.json"
        if folder.name == "studio-preview" or not spec_file.is_file():
            continue
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*$", folder.name):
            continue
        try:
            spec = json.loads(spec_file.read_text(encoding="utf-8"))
        except ValueError:
            continue
        stat = spec_file.stat()
        items.append({
            "version": folder.name, "candidate": folder.name,
            "current": folder.name == current_dir,
            "label": folder.name,
            "iso": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%m-%d %H:%M:%S"),
            "bytes": stat.st_size,
            "kind": spec.get("kind") or "", "key": spec.get("key") or "",
        })
    current = next((x for x in items if x["current"]), None)
    others = sorted([x for x in items if not x["current"]], key=lambda x: x["mtime"], reverse=True)
    ordered = ([current] if current else []) + others
    rel = spec_path.relative_to(Path(root).resolve()).as_posix()
    return {
        "ok": True, "path": rel, "type": "design", "kind": current.get("kind") if current else "",
        "limit": PAGE_HISTORY_LIMIT, "max": 0,
        "history_count": len(others), "current": current, "items": ordered,
    }


def read_design_history(root, path, version):
    spec_path = _design_spec_path(root, path)
    item = _design_version(root, spec_path, version)
    base = Path(root).resolve()
    item["path"] = (spec_path.parent.parent / item["version"] / "spec.json").relative_to(base).as_posix()
    item["basePath"] = spec_path.relative_to(base).as_posix()
    return {"ok": True, "type": "design", **item}


def diff_design_history(root, path, left, right):
    left = str(left or "")
    right = str(right or "")
    if left == right:
        raise StudioError("DIFF_SAME", "请选择两个不同的候选版本进行对比")
    spec_path = _design_spec_path(root, path)
    left_item = _design_version(root, spec_path, left)
    right_item = _design_version(root, spec_path, right)
    rel = spec_path.parent.parent.relative_to(Path(root).resolve()).as_posix()
    return _diff_payload(rel, "json", left_item, right_item)


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
