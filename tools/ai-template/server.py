#!/usr/bin/env python3
"""A4 本机工作台：127.0.0.1 静态页 + 审批/管理处 JSON API，不访问外网。"""
from __future__ import annotations

import json
import importlib.util
import mimetypes
import re
import sys
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))


def _load_local(name, filename):
    """按文件路径加载，避免与仓库根/测试同名模块冲突。"""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


compiler = _load_local("ai_template_compiler", "compiler.py")
display = _load_local("ai_template_display", "display.py")
generate = _load_local("ai_template_generate", "generate.py")
preview = _load_local("ai_template_preview", "preview.py")
publish = _load_local("ai_template_publish", "publish.py")
registry = _load_local("ai_template_registry", "registry.py")
site_store = _load_local("ai_template_site_store", "site_store.py")

DRAFTS = "tools/ai-template/drafts"
WORKBENCH = HERE / "workbench"
MAX_BODY = 1024 * 1024
FILE_URI = re.compile(r"file://([^\"']+)")


def _relative(path, root):
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve()))
    except ValueError:
        return str(path)


def _safe_path(root, rel):
    path = (Path(root) / rel).resolve()
    try:
        path.relative_to(Path(root).resolve())
    except ValueError:
        return None
    return path


def candidates(root=ROOT):
    items = []
    drafts = Path(root) / DRAFTS
    if not drafts.exists():
        return items
    for spec_path in sorted(drafts.glob("*/candidate-*/spec.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        kind = spec.get("kind")
        if kind not in ("layout", "theme"):
            continue
        key = spec.get("key") or spec_path.parent.parent.name
        candidate = spec_path.parent.name
        metrics_path = spec_path.parent / "metrics.json"
        metrics = None
        if metrics_path.exists():
            try:
                metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            except ValueError:
                metrics = None
        gates = metrics.get("gates", []) if metrics else []
        errors = [{"code": g.get("code"), "message": g.get("message")}
                  for g in gates if not g.get("ok")]
        g6 = ""
        for g in gates:
            if g.get("gate") == "G6" and g.get("ok"):
                g6 = g.get("message") or "ok"
        shots_data = (metrics or {}).get("shots", [])
        overflow = max([int(s.get("overflow") or 0) for s in shots_data] or [0])
        dhash = ""
        for g in gates:
            if g.get("gate") == "G6" and "dHash" in str(g.get("message", "")):
                dhash = g.get("diff", "")
        visual = metrics.get("visual") if metrics else "not-run"
        ok = bool(metrics and metrics.get("ok") and visual == "checked")
        items.append({
            "key": key, "name": spec.get("name") or key, "kind": kind,
            "path": _relative(spec_path, root),
            "candidate": candidate,
            "preview": "/preview/%s/%s/%s/" % (kind, key, candidate),
            "ok": ok, "visual": visual,
            "cssBytes": (metrics or {}).get("metrics", {}).get("cssBytes"),
            "shots": (metrics or {}).get("metrics", {}).get("shots"),
            "overflow": overflow, "dhash": dhash,
            "intent": spec.get("intent", ""),
            "archetype": spec.get("archetype", ""),
            "rationale": spec.get("rationale", []),
            "spec": spec,
            "gates": gates, "g6": g6,
            "errors": errors or ([] if metrics else [{"code": "GATES_MISSING", "message": "未跑 preview"}]),
            "at": spec_path.stat().st_mtime,
        })
    return items


def _rewrite_file_uris(text, root):
    root_uri = Path(root).resolve().as_uri()

    def repl(match):
        raw = urllib.parse.unquote(match.group(1))
        path = Path(raw)
        try:
            rel = path.resolve().relative_to(Path(root).resolve())
        except ValueError:
            return match.group(0)
        return "/repo/" + rel.as_posix()

    text = text.replace(root_uri + "/", "/repo/")
    return FILE_URI.sub(repl, text)


class Handler(BaseHTTPRequestHandler):
    root = ROOT

    def log_message(self, fmt, *args):
        # 本机工作台不刷屏；保留 4xx/5xx 便于排查
        if args and str(args[1] if len(args) > 1 else "").startswith(("4", "5")):
            super().log_message(fmt, *args)

    def _send(self, status, body, content_type="text/plain; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload, status=200):
        self._send(status, json.dumps(payload, ensure_ascii=False), "application/json; charset=utf-8")

    def _file(self, path):
        if not path or not path.exists() or not path.is_file():
            self._send(404, "not found")
            return
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        self._send(200, path.read_bytes(), ctype)

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path in ("/", "/review", "/review.html"):
            self._file(WORKBENCH / "review.html")
            return
        if path in ("/manage", "/manage.html"):
            self._file(WORKBENCH / "manage.html")
            return
        if path.startswith("/workbench/"):
            self._file(_safe_path(WORKBENCH, path[len("/workbench/"):]))
            return
        if path.startswith("/repo/"):
            self._file(_safe_path(self.root, path[len("/repo/"):]))
            return
        if path.startswith("/preview/"):
            self._preview(path)
            return
        if path == "/api/candidates":
            self._json({"ok": True, "items": candidates(self.root)})
            return
        if path == "/api/manage":
            self._json(display.manage_payload(self.root))
            return
        if path == "/favicon.ico":
            self._send(204, b"")
            return
        self._send(404, "not found")

    def _preview(self, path):
        parts = [p for p in path.strip("/").split("/") if p]
        if len(parts) < 4:
            self._send(404, "preview not found")
            return
        kind, key, candidate = parts[1], parts[2], parts[3]
        if kind not in ("layout", "theme"):
            self._send(404, "preview not found")
            return
        base = Path(self.root) / DRAFTS / key / candidate
        html = base / "preview" / "index.html"
        if not html.exists():
            self._send(404, "preview not found")
            return
        text = _rewrite_file_uris(html.read_text(encoding="utf-8"), self.root)
        self._send(200, text, "text/html; charset=utf-8")

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        if not path.startswith("/api/"):
            self._send(404, "not found")
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._send(400, "bad length")
            return
        if length > MAX_BODY:
            self._send(413, "body too large")
            return
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except ValueError:
            self._send(400, "bad json")
            return
        if not isinstance(body, dict):
            self._send(400, "body must be object")
            return
        try:
            if path == "/api/approve":
                result = publish.approve_candidate(
                    _safe_path(self.root, body.get("path", "")), body.get("reviewer"),
                    root=self.root, note=body.get("note", ""), model=body.get("model", ""),
                    prompt_id=body.get("prompt_id", "generate-v1"),
                    rounds=int(body.get("rounds") or 1),
                )
                if body.get("push"):
                    try:
                        pushed = display.set_visible(result["kind"], result["key"], True, root=self.root)
                        result["pushed"] = bool(pushed.get("changed"))
                    except display.DisplayError as exc:
                        result["pushed"] = False
                        result["push_code"] = exc.code
                        result["push_message"] = exc.message
            elif path == "/api/reject":
                result = publish.reject_candidate(
                    _safe_path(self.root, body.get("path", "")), body.get("reviewer"),
                    body.get("reason"), body.get("note", ""), root=self.root,
                )
            elif path == "/api/generate":
                count = int(body.get("count") or 1)
                try:
                    result = generate.generate(
                        body.get("kind"), body.get("request"), body.get("constraints", ""),
                        mock=bool(body.get("mock")), expect=count,
                        out_dir=Path(self.root) / DRAFTS,
                        cache_dir=Path(self.root) / "tools" / "ai-template" / "cache",
                    )
                except generate.GenerationError as exc:
                    result = {"ok": False, "code": "GENERATE", "message": "; ".join(exc.errors),
                              "errors": exc.errors}
            elif path == "/api/revise":
                old_path = _safe_path(self.root, body.get("path", ""))
                if old_path is None:
                    raise publish.PublishError("REVISE_PATH", "候选路径不合法")
                max_rounds = int(body.get("max_rounds") or 3)
                if publish.revision_count(old_path, root=self.root) >= max_rounds:
                    raise publish.PublishError("REVISE_LIMIT", "该设计已迭代 %d 轮，转人工设计" % max_rounds)
                try:
                    result = generate.regenerate(
                        old_path, body.get("comments"), mock=bool(body.get("mock")),
                        out_dir=Path(self.root) / DRAFTS,
                        cache_dir=Path(self.root) / "tools" / "ai-template" / "cache",
                    )
                except generate.GenerationError as exc:
                    result = {"ok": False, "code": "REVISE", "message": "; ".join(exc.errors),
                              "errors": exc.errors}
                else:
                    review = publish.record_revision(
                        result["spec_path"], body.get("comments"), body.get("reviewer", ""),
                        root=self.root, max_rounds=max_rounds,
                    )
                    result.update({"review": review["review"], "round": review["round"]})
            elif path == "/api/preview":
                spec_path = _safe_path(self.root, body.get("path", ""))
                if spec_path is None:
                    raise publish.PublishError("PREVIEW_PATH", "候选路径不合法")
                spec = compiler.load_json(spec_path)
                kind = body.get("kind") or spec.get("kind")
                report = preview.evaluate(spec, kind, spec_path.parent,
                                          no_shot=bool(body.get("noShot")), quick=bool(body.get("quick")))
                preview.metrics.write_report(spec_path.parent / "metrics.json", report)
                result = {"ok": bool(report.get("ok")), "visual": report.get("visual"), "key": report.get("key"),
                          "gates": report.get("gates", []), "metrics": report.get("metrics", {})}
            elif path == "/api/spec/save":
                result = generate.save_manual(
                    _safe_path(self.root, body.get("path", "")), body.get("spec"),
                )
            elif path == "/api/clone":
                result = generate.clone_published(
                    body.get("kind"), body.get("key"), body.get("new_key"), body.get("new_name"),
                    docs_dir=Path(self.root) / "docs" / "templates",
                    out_dir=Path(self.root) / DRAFTS,
                )
            elif path == "/api/archive":
                kind, key = body.get("kind"), body.get("key")
                hidden = display.set_visible(kind, key, False, root=self.root)
                archived = registry.archive(kind, key, root=self.root)
                result = dict(archived, hidden=hidden.get("changed", False))
            elif path == "/api/display":
                result = display.set_visible(body.get("kind"), body.get("key"),
                                             bool(body.get("on")), root=self.root)
            elif path == "/api/display/limit":
                result = display.set_limit(body.get("kind"), body.get("max"), root=self.root)
            elif path == "/api/reorder":
                result = display.reorder(body.get("kind"), body.get("key"),
                                         int(body.get("direction") or 0), root=self.root)
            else:
                self._send(404, "not found")
                return
        except (publish.PublishError, display.DisplayError) as exc:
            self._json(exc.as_dict())
            return
        except generate.GenerationError as exc:
            self._json({"ok": False, "code": "GENERATE", "message": "; ".join(exc.errors),
                        "errors": exc.errors})
            return
        except Exception as exc:
            traceback.print_exc()
            self._json({"ok": False, "code": "SERVER_ERROR", "message": str(exc)}, 500)
            return
        self._json(result)


def make_server(port=8787, root=ROOT):
    class Bound(Handler):
        pass
    Bound.root = root
    server = ThreadingHTTPServer(("127.0.0.1", int(port)), Bound)
    server.daemon_threads = True
    return server


def serve(port=8787, root=ROOT):
    server = make_server(port, root)
    print("工作台已启动:http://127.0.0.1:%d/  (Ctrl+C 停止)" % server.server_address[1])
    print("管理处:http://127.0.0.1:%d/manage.html" % server.server_address[1])
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
