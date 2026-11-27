#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
采集交互页的本地服务

启动:  python3 collector/server.py [端口] [--api-only]      默认 8765
       (在 collector/ 目录内时也可直接 python3 server.py)
访问:  http://127.0.0.1:8765/collect.html

代码位于 collector/,展示页面与数据位于项目根;本服务默认托管项目根,
并把 /collect.html 映射到 collector/collect.html(两种路径都可访问)。

提供:
  GET  /collect.html           采集交互页(实际文件 collector/collect.html)
  GET  /api/health             后端健康检测(供采集页启动时探测)
  POST /api/collect            触发采集(调用 generate.py 的纯规则程序)
                               mode=keyword|url|batch,支持 B站/公众号/小红书
  GET  /api/topics             列出已有主题(含最近采集时间与方式)
  GET  /api/intake?id=         读取某单元上次填写的采集信息 + 最近采集记录(重新采集回填用)
  POST /api/title              只更新显示标题,不重新采集内容
  GET  /*                      静态文件托管(首页/子页/数据)

运行角色(便于采集端与展示端分离部署,同机/同容器下共享数据目录):
  --api-only  采集端专用模式:只提供 /api/* 与 /collect.html,不再托管静态首页/子页,
             静态展示交给独立的 Web 服务器(如 Nginx)。默认(不带该参数)为全功能模式,
             向后兼容。也可用环境变量 SERVER_ROLE=api 指定。
说明: 接口路径支持带任意前缀(如部署在子路径 /app/ 下时 /app/api/collect 同样有效)。
"""

import argparse
import datetime
import hmac
import http.server
import ipaddress
import json
import os
import re
import secrets
import socket
import socketserver
import sys
import threading
import uuid
import urllib.parse

import generate
import git_sync
import settings_store

# 采集代码位于 <项目根>/collector/,展示页面与数据在项目根。
# ROOT 指向项目根用于静态托管;COLLECTOR_DIR 指向本目录用于定位采集页。
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = (os.environ.get("VIDEO_PROJECT_ROOT") or "").strip() or os.path.dirname(SCRIPT_DIR)
ROOT = os.path.abspath(ROOT)
COLLECTOR_DIR = SCRIPT_DIR

# 运行角色:full=静态+接口全托管(默认);api=仅接口+采集页(展示端由独立 Web 服务器提供)
API_ONLY = False
# 公网模式:绑定 0.0.0.0 且所有写接口必须带访问口令;默认本机模式不校验
PUBLIC_MODE = False
TOKEN = ""
# 本机设置页 CSRF token：每次启动生成，GET /api/settings 下发，写接口回传
CSRF_TOKEN = secrets.token_urlsafe(24)


def origin_host_allowed(host):
    """设置页 Origin 白名单：本机、内网 IP 与 .local 主机名。"""
    host = (host or "").strip().strip("[]").lower()
    if not host:
        return False
    if host in ("127.0.0.1", "localhost", "::1"):
        return True
    if host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback


def lan_ip():
    """尽力获取本机一个局域网 IPv4 地址；失败返回空串。"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        addr = sock.getsockname()[0]
        sock.close()
        if ipaddress.ip_address(addr).is_link_local:
            return ""
        return addr
    except (OSError, ValueError):
        return ""
JOBS = {}
JOBS_LOCK = threading.Lock()


def _new_job(kind):
    job_id = uuid.uuid4().hex[:12]
    with JOBS_LOCK:
        JOBS[job_id] = {
            "id": job_id, "kind": kind, "state": "running",
            "progress": "", "logs": [], "result": None, "created": generate.now_stamp(),
        }
    return job_id


def _job_update(job_id, *, state=None, progress=None, log=None, result=None):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        if state:
            job["state"] = state
        if progress is not None:
            job["progress"] = progress
        if log:
            job["logs"].append(str(log))
            job["logs"] = job["logs"][-200:]
        if result is not None:
            job["result"] = result



class Handler(http.server.SimpleHTTPRequestHandler):
    # 静态托管白名单:只放行展示页与 assets,其余(源码/文档/备份/.git)一律 404
    STATIC_EXACT = {
        "/", "/index.html", "/series.html", "/list.html", "/single.html", "/mine-io.html",
        "/collector/collect.html", "/collect.html",
        "/collector/settings.html", "/settings.html",
        "/collector/settings-guide.html", "/settings-guide.html",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def _static_allowed(self, path):
        clean = path.split("?", 1)[0].split("#", 1)[0]
        if clean in self.STATIC_EXACT:
            return True
        if clean.startswith("/assets/") and ".py" not in clean:
            return True
        return False

    def _token_ok(self):
        supplied = self.headers.get("X-Collect-Token") or ""
        if not supplied:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            supplied = (qs.get("token") or [""])[0]
        return bool(TOKEN) and hmac.compare_digest(supplied, TOKEN)

    def _settings_origin_ok(self):
        origin = self.headers.get("Origin") or ""
        if not origin:
            return True
        try:
            parsed = urllib.parse.urlparse(origin)
        except ValueError:
            return False
        if parsed.scheme not in ("http", "https"):
            return False
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        return origin_host_allowed(parsed.hostname) and port == self.server.server_address[1]

    def _csrf_ok(self):
        supplied = self.headers.get("X-CSRF-Token") or ""
        return self._settings_origin_ok() and bool(supplied) and hmac.compare_digest(supplied, CSRF_TOKEN)

    def translate_path(self, path):
        # 兼容旧访问路径:/collect.html 现在实际位于 collector/collect.html。
        # 同时保留 /collector/collect.html 的自然路径。
        clean = (path or "").split("?", 1)[0].split("#", 1)[0]
        tail = clean.rstrip("/").split("/")[-1]
        if tail in ("collect.html", "settings.html", "settings-guide.html") and not clean.startswith("/collector/"):
            return os.path.join(COLLECTOR_DIR, tail)
        return super().translate_path(path)

    def log_message(self, fmt, *args):
        # 只打印简单访问日志,避免刷屏
        if "/api/" in (self.path or ""):
            return
        super().log_message(fmt, *args)

    def end_headers(self):
        # 缓存分层(D17):页面与数据必须 no-store(采集更新后手机浏览器若缓存 index.js 会一直显示旧首页);
        # 样式/脚本/图片属静态资源,允许短缓存减少重复加载。
        path = (self.path or "").split("?", 1)[0]
        if path.endswith((".css", ".js")) and not path.startswith("/assets/data/"):
            self.send_header("Cache-Control", "public, max-age=300")
        elif path.endswith((".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico")):
            self.send_header("Cache-Control", "public, max-age=86400")
        else:
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length else "{}"
        return json.loads(body)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path.endswith("/api/health"):
            # 采集只写数据:数据目录 + 采集单元目录,两处都可写才算健康
            data_ok = os.access(generate.DATA_DIR, os.W_OK)
            coll_ok = os.access(generate.COLLECTIONS_DIR, os.W_OK)
            idx = generate.index_status()
            info = {
                "ok": True,
                "writable": data_ok and coll_ok,
                "data_writable": data_ok,
                "collections_writable": coll_ok,
                # 索引可读性单独上报:损坏时不要让前端误以为「站里没有内容」
                "index_ok": idx["ok"],
                "index_count": idx["count"],
                "index_error": idx["reason"],
                "role": "api" if API_ONLY else "full",
                "auth": "token" if PUBLIC_MODE else "none",
            }
            # 公网模式不回显本机路径,避免泄露部署结构
            if not PUBLIC_MODE:
                info["data_dir"] = generate.DATA_DIR
                info["collections_dir"] = generate.COLLECTIONS_DIR
            self._json(info)
            return
        if path.endswith("/api/site"):
            try:
                cfg = generate.normalize_site_config(generate.load_site_config())
            except ValueError as exc:
                self._json({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}, 400)
                return
            self._json({"ok": True, "site": cfg, "csrf_token": CSRF_TOKEN,
                        "updated": datetime.date.today().isoformat()})
            return
        if path.endswith("/api/settings"):
            try:
                data = settings_store.public_settings()
                data["csrf_token"] = CSRF_TOKEN
                data["git"] = git_sync.status()
            except ValueError as exc:
                self._json({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}, 400)
            else:
                self._json(data)
            return
        if path.endswith("/api/actions/export"):
            self._json(settings_store.export_cron())
            return
        if path.endswith("/api/git/status"):
            self._json(git_sync.status())
            return
        if "/api/jobs/" in path:
            job_id = path.rsplit("/", 1)[-1]
            with JOBS_LOCK:
                job = JOBS.get(job_id)
            if not job:
                self._json({"ok": False, "error": {"code": "NOT_FOUND", "message": "任务不存在"}}, 404)
                return
            self._json({"ok": True, **job})
            return
        if "/api/git/jobs/" in path:
            job_id = path.rsplit("/", 1)[-1]
            with JOBS_LOCK:
                job = JOBS.get(job_id)
            if not job:
                self._json({"ok": False, "error": {"code": "NOT_FOUND", "message": "任务不存在"}}, 404)
                return
            self._json({"ok": True, **job})
            return
        if path.endswith("/api/topics"):
            status = generate.index_status()
            if not status["ok"]:
                self._json({
                    "ok": False,
                    "error": "采集索引不可用: " + (status["reason"] or "未知原因"),
                    "topics": [],
                }, 500)
                return
            index = generate.load_index()
            site_ed = generate.load_site_config().get("editorial") or {}
            try:
                sections_payload = generate.build_sections_payload(index)
            except Exception:
                sections_payload = []
            section_titles = {s.get("id"): s.get("title", "") for s in sections_payload}
            self._json({"ok": True, "sections": sections_payload, "topics": [
                {
                    "id": t.get("id"),
                    "title": t.get("title"),
                    "type": t.get("type", "series"),
                    "enabled": t.get("enabled", True),
                    "count": t.get("count", 0),
                    # D24:page 由 type 推导,platform 由稳定 key 翻成中文展示名
                    "page": unit_page(t),
                    "author": (t.get("source") or {}).get("name", ""),
                    "platform": generate.platform_label((t.get("source") or {}).get("platform")),
                    "keyword": t.get("keyword", ""),
                    "tags": t.get("tags") or [],
                    "section": t.get("section", ""),
                    "section_title": section_titles.get(t.get("section", ""), ""),
                    "created": t.get("created", ""),
                    "updated": t.get("updated", ""),
                    "last_at": t.get("last_at", ""),
                    "last_mode": t.get("last_mode", ""),
                    "last_mode_label": t.get("last_mode_label", ""),
                    "pin": bool((site_ed.get(str(t.get("id")) or "") or {}).get("pin")),
                    "hero_image": (site_ed.get(str(t.get("id")) or "") or {}).get("hero_image", ""),
                } for t in index
            ]})
            return
        if path.endswith("/api/intake"):
            # 重新采集前的回填:返回该单元上次填写的采集信息 + 最近几次采集记录
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            unit_id = (qs.get("id") or [""])[0].strip()
            if not unit_id:
                self._json({"ok": False, "error": "缺少单元 id"}, 400)
                return
            if not generate.valid_unit_id(unit_id):
                self._json({"ok": False, "error": "单元 id 不合法"}, 400)
                return
            data = generate.load_collection_data(unit_id)
            if data is None:
                self._json({"ok": False, "error": "未找到采集单元: %s" % unit_id}, 404)
                return
            meta = next((t for t in generate.load_index() if t.get("id") == unit_id), None) or {}
            videos = data.get("videos") or []
            self._json({
                "ok": True,
                "id": unit_id,
                "intake": data.get("intake") or {},
                "runs": data.get("runs") or [],
                # 老单元没有采集记录时,用现有条目的原链接回填批量输入框
                "links": [v.get("url", "") for v in videos if v.get("url")][:60],
                "unit": {
                    "id": unit_id,
                    "title": data.get("title", ""),
                    "type": data.get("type", "series"),
                    "platform": generate.platform_label((data.get("source") or {}).get("platform")),
                    "count": len(data.get("videos") or []),
                    "section": data.get("section") or "",
                    "page": unit_page(data or meta),
                    # 老单元没有采集记录时,至少能用当初的关键词/链接回填
                    "keyword": data.get("keyword") or meta.get("keyword", ""),
                    "last_at": meta.get("last_at", ""),
                    # 当前是否在首页显示:重新采集态据此显示「下线不显示 / 重新上线显示」
                    "enabled": meta.get("enabled", True) is not False,
                },
            })
            return
        # 未知 /api/ 路径一律返回 JSON,避免 Python 默认 HTML 404 让前端 json() 解析失败
        if "/api/" in path:
            self._json({"ok": False, "error": "未知接口: %s" % path}, 404)
            return
        # 采集端专用模式:只放行采集页本身和它依赖的样式表,其他静态文件由展示端 Web 服务器提供
        if API_ONLY:
            tail = path.rstrip("/").split("/")[-1]
            if tail in ("collect.html", "settings.html", "settings-guide.html", "style.css"):
                return super().do_GET()
            self._json({
                "ok": False,
                "error": "当前为采集端专用模式(api-only),静态展示请访问独立的展示站服务",
                "hint": "采集页仍是 /collect.html",
            }, 404)
            return
        if not self._static_allowed(path):
            self._json({
                "ok": False,
                "error": "未对外开放的路径",
                "hint": "静态托管只放行展示页、我的导入导出页与 assets/;采集接口需本机启动或带 token",
            }, 404)
            return
        return super().do_GET()

    def do_PUT(self):
        path = urllib.parse.urlparse(self.path).path
        section_prefix = "/api/settings/sections/"
        topic_prefix = "/api/settings/topics/"
        if not (path.endswith("/api/settings") or path.endswith("/api/site") or
                path.startswith(section_prefix) or path.startswith(topic_prefix)):
            self._json({"ok": False, "error": {"code": "NOT_FOUND", "message": "未知接口"}}, 404)
            return
        if not self._csrf_ok():
            self._json({"ok": False, "error": {"code": "CSRF_FAILED", "message": "CSRF token 或 Origin 校验失败"}}, 403)
            return
        try:
            payload = self._read_json()
            if path.endswith("/api/site"):
                result = {"ok": True, "site": generate.save_site_patch(payload)}
            elif path.startswith(section_prefix):
                section_id = urllib.parse.unquote(path[len(section_prefix):]).strip("/")
                if not section_id:
                    raise ValueError("缺少板块 id")
                result = settings_store.save_section(section_id, payload)
            elif path.startswith(topic_prefix):
                topic_id = urllib.parse.unquote(path[len(topic_prefix):]).strip("/")
                if not topic_id:
                    raise ValueError("缺少主题 id")
                result = settings_store.save_topic(topic_id, payload)
            else:
                result = settings_store.save_settings(payload)
        except ValueError as exc:
            self._json({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}, 400)
            return
        except Exception as exc:
            self._json({"ok": False, "error": {"code": "INTERNAL", "message": str(exc)}}, 500)
            return
        self._json(result)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        # 公网模式:所有写接口都必须带访问口令;本机默认不校验
        if PUBLIC_MODE and not self._token_ok():
            self._json({"ok": False, "error": "访问口令无效或缺失,请先填写 token"}, 401)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8") if length else "{}"
            payload = json.loads(body)
        except Exception as exc:
            self._json({"ok": False, "error": "请求参数错误: %s" % exc}, 400)
            return

        if path.endswith("/api/site"):
            if not self._csrf_ok():
                self._json({"ok": False, "error": {"code": "CSRF_FAILED", "message": "CSRF token 或 Origin 校验失败"}}, 403)
                return
            try:
                site = generate.save_site_patch(payload)
            except ValueError as exc:
                self._json({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}, 400)
                return
            self._json({"ok": True, "site": site})
            return
        # 只改单元元数据(标题/板块/标签/显示/置顶/大图),不触发采集
        if path.endswith("/api/unit/meta"):
            if not self._csrf_ok():
                self._json({"ok": False, "error": {"code": "CSRF_FAILED", "message": "CSRF token 或 Origin 校验失败"}}, 403)
                return
            unit_id = (payload.get("id") or "").strip()
            if not generate.valid_unit_id(unit_id):
                self._json({"ok": False, "error": "单元 id 不合法"}, 400)
                return
            if "pin" in payload and not isinstance(payload.get("pin"), bool):
                self._json({"ok": False, "error": "pin 必须是布尔值"}, 400)
                return
            meta_kw = {}
            for key in ("title", "section", "tags", "enabled"):
                if key in payload:
                    meta_kw[key] = payload.get(key)
            try:
                result = generate.update_unit_meta(unit_id, **meta_kw)
                if not result.get("ok"):
                    status = 404 if "未找到" in (result.get("error") or "") else 400
                    self._json(result, status)
                    return
                if "pin" in payload or "hero_image" in payload:
                    patch = {"id": unit_id}
                    if "pin" in payload:
                        patch["pin"] = payload.get("pin")
                    if "hero_image" in payload:
                        patch["hero_image"] = str(payload.get("hero_image") or "").strip()
                    site = generate.save_site_patch(patch)
                    result["site"] = site
                    entry = (site.get("editorial") or {}).get(unit_id) or {}
                    result["pin"] = bool(entry.get("pin"))
                    result["hero_image"] = entry.get("hero_image", "")
            except ValueError as exc:
                self._json({"ok": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}}, 400)
                return
            except Exception as exc:
                self._json({"ok": False, "error": {"code": "INTERNAL", "message": str(exc)}}, 500)
                return
            self._json(result)
            return
        # 开启/关闭某采集单元的显示
        if path.endswith("/api/scheduler/toggle"):
            if not self._csrf_ok():
                self._json({"ok": False, "error": {"code": "CSRF_FAILED", "message": "CSRF token 或 Origin 校验失败"}}, 403)
                return
            # v1：Actions schedule 已固定运行，本机调度默认关闭
            self._json({"ok": False, "error": {
                "code": "CONFLICT",
                "message": "Actions schedule 已启用，本机调度默认关闭；停用线上 cron 后才能开启本机调度",
            }}, 409)
            return
        if path.endswith("/api/run-now"):
            if not self._csrf_ok():
                self._json({"ok": False, "error": {"code": "CSRF_FAILED", "message": "CSRF token 或 Origin 校验失败"}}, 403)
                return
            pages = int(payload.get("pages") or settings_store.actions_schedule().get("pages") or 3)
            job_id = _new_job("collect")
            def run():
                logs = []
                def log(msg):
                    logs.append(str(msg))
                    _job_update(job_id, progress=str(msg), log=msg)
                try:
                    result = generate.run_topics([generate.TOPICS_FILE], pages=pages, log=log)
                    state = "success" if result.get("ok") else "failed"
                    _job_update(job_id, state=state, result=result, progress="完成")
                except Exception as exc:
                    _job_update(job_id, state="failed", progress="失败",
                                log="采集异常: %s" % exc, result={"ok": False, "error": str(exc)})
            threading.Thread(target=run, daemon=True).start()
            self._json({"ok": True, "job_id": job_id}, 202)
            return
        if path.endswith("/api/git/preview"):
            if not self._csrf_ok():
                self._json({"ok": False, "error": {"code": "CSRF_FAILED", "message": "CSRF token 或 Origin 校验失败"}}, 403)
                return
            self._json(git_sync.preview())
            return
        if path.endswith("/api/git/push"):
            if not self._csrf_ok():
                self._json({"ok": False, "error": {"code": "CSRF_FAILED", "message": "CSRF token 或 Origin 校验失败"}}, 403)
                return
            job_id = _new_job("git")
            def push():
                logs = []
                def log(msg):
                    _job_update(job_id, progress=str(msg), log=msg)
                # git_sync.push 内部已有日志；这里只做状态收口
                try:
                    result = git_sync.push()
                    state = "success" if result.get("ok") else result.get("state", "failed")
                    _job_update(job_id, state=state, result=result, progress="完成")
                except Exception as exc:
                    _job_update(job_id, state="failed", progress="失败",
                                log="推送异常: %s" % exc, result={"ok": False, "error": str(exc)})
            threading.Thread(target=push, daemon=True).start()
            self._json({"ok": True, "job_id": job_id}, 202)
            return

        # 开启/关闭某采集单元的显示
        if path.endswith("/api/toggle"):
            unit_id = (payload.get("id") or "").strip()
            if not unit_id:
                self._json({"ok": False, "error": "缺少单元 id"}, 400)
                return
            if not generate.valid_unit_id(unit_id):
                self._json({"ok": False, "error": "单元 id 不合法"}, 400)
                return
            enabled = bool(payload.get("enabled"))
            try:
                result = generate.set_enabled(unit_id, enabled)
            except Exception as exc:
                self._json({"ok": False, "error": "切换显示失败: %s" % exc}, 500)
                return
            self._json(result, 200 if result.get("ok") else 404)
            return

        # 只更新显示标题,不重新采集内容
        if path.endswith("/api/title"):
            unit_id = (payload.get("id") or "").strip()
            title = (payload.get("title") or "").strip()
            if not generate.valid_unit_id(unit_id):
                self._json({"ok": False, "error": "单元 id 不合法"}, 400)
                return
            result = generate.update_title(unit_id, title)
            self._json(result, 200 if result.get("ok") else 400)
            return

        if not path.endswith("/api/collect"):
            self._json({"ok": False, "error": "未知接口"}, 404)
            return

        keyword = (payload.get("keyword") or "").strip()
        mode = (payload.get("mode") or "keyword").strip()
        # 归属板块:可留空(未分类);非空时必须存在于 sections.yml
        section = (payload.get("section") or "").strip() or None
        if section and section not in generate.section_ids():
            self._json({"ok": False, "error": "板块不存在: %s" % section}, 400)
            return
        # 采集方式:append(默认,追加保留旧条目)| replace(覆盖,只保留本次结果)
        # | remove(按填写的链接从已有单元移除条目,仅链接类采集可用)
        merge_mode = (payload.get("merge_mode") or "append").strip()
        if merge_mode not in ("append", "replace", "remove"):
            self._json({"ok": False, "error": "不支持的采集方式: %s" % merge_mode}, 400)
            return
        # 覆盖只对已有单元有意义;新建时强制按追加处理,避免误传参数造成空结果
        unit_id_raw = (payload.get("unit_id") or payload.get("slug") or "").strip()
        replace = merge_mode == "replace" and bool(unit_id_raw)
        if not keyword:
            if mode == "batch":
                hint = "请粘贴至少一条链接"
            elif mode == "url":
                hint = "内容链接不能为空"
            else:
                hint = "主题关键词不能为空"
            self._json({"ok": False, "error": hint}, 400)
            return
        # 移除链接:只按填写的链接做本地匹配,不重新抓取内容;主题采集没有单条链接可移除
        if merge_mode == "remove":
            if mode == "keyword":
                self._json({"ok": False, "error": "按主题采集不支持移除链接,请切换到按链接或批量链接"}, 400)
                return
            if not unit_id_raw:
                self._json({"ok": False, "error": "移除链接必须指定要操作的采集单元"}, 400)
                return
            logs = []
            result = generate.remove_links(
                text=keyword, unit_id=unit_id_raw, mode=mode,
                dry_run=bool(payload.get("dry_run")), log=lambda m: logs.append(str(m)),
            )
            result["logs"] = logs
            self._json(result, 200 if result.get("ok") else 400)
            return

        # 批量采集的显示标题是必填项(前端已有默认值,这里再兜一层)
        if mode == "batch" and not (payload.get("title") or "").strip():
            self._json({"ok": False, "error": "请填写显示标题(批量采集必填,可用自动生成的默认值)"}, 400)
            return

        # 手工补录字段(公众号/小红书抓取被风控时使用)
        manual = {
            "title": (payload.get("manual_title") or "").strip() or None,
            "author": (payload.get("manual_author") or "").strip() or None,
            "desc": (payload.get("manual_desc") or "").strip() or None,
            "date": (payload.get("manual_date") or "").strip() or None,
            "cover": (payload.get("manual_cover") or "").strip() or None,
        }

        # 本次采集的填写信息:写入单元,下次重新采集时原样回填
        intake = generate.normalize_intake({
            "mode": mode,
            "input": keyword,
            "title": payload.get("title"),
            "up": payload.get("up"),
            "pages": payload.get("pages"),
            "channels": payload.get("channels"),
            "manual_title": manual["title"], "manual_author": manual["author"],
            "manual_desc": manual["desc"], "manual_date": manual["date"],
            "manual_cover": manual["cover"],
        })

        # 收集日志,随响应返回给前端展示
        logs = []
        def log(msg):
            logs.append(str(msg))

        try:
            if mode == "batch":
                result = generate.collect_batch(
                    text=keyword,
                    title=(payload.get("title") or "").strip() or None,
                    unit_id=(payload.get("unit_id") or payload.get("slug") or "").strip() or None,
                    slogan=(payload.get("slogan") or "").strip() or None,
                    dry_run=bool(payload.get("dry_run")),
                    log=log,
                    intake=intake, replace=replace, section=section,
                )
            elif mode == "url":
                result = generate.collect_by_url(
                    url=keyword,
                    title=(payload.get("title") or "").strip() or None,
                    unit_id=(payload.get("unit_id") or payload.get("slug") or "").strip() or None,
                    slogan=(payload.get("slogan") or "").strip() or None,
                    dry_run=bool(payload.get("dry_run")),
                    manual=manual,
                    log=log,
                    intake=intake, replace=replace, section=section,
                )
            else:
                result = generate.collect_topic(
                    keyword=keyword,
                    pages=int(payload.get("pages") or 30),
                    title=(payload.get("title") or "").strip() or None,
                    up=(payload.get("up") or "").strip() or None,
                    unit_id=(payload.get("unit_id") or payload.get("slug") or "").strip() or None,
                    slogan=(payload.get("slogan") or "").strip() or None,
                    dry_run=bool(payload.get("dry_run")),
                    topic_channels=payload.get("channels"),
                    log=log,
                    intake=intake, replace=replace, section=section,
                )
        except Exception as exc:
            self._json({"ok": False, "error": "采集失败: %s" % exc, "logs": logs}, 500)
            return

        result["logs"] = logs
        self._json(result, 200 if result.get("ok") else 500)


# 允许端口复用 + 多线程:一个长采集不再阻塞页面/健康检查等其它请求
class ReusableTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def unit_page(t):
    """单元详情页路由:类型决定页面,不在数据/索引里存表现层 page 字段"""
    unit_type = (t or {}).get("type") or "series"
    return ("single.html?id=%s" if unit_type == "single" else "series.html?id=%s") % (t or {}).get("id", "")


def main():
    global API_ONLY, PUBLIC_MODE, TOKEN
    ap = argparse.ArgumentParser(description="集页采集服务(默认只监听本机,不对外)")
    ap.add_argument("port_pos", nargs="?", default=None, help="端口(兼容旧的数字位置参数)")
    ap.add_argument("--port", type=int, default=None, help="端口,默认 8765(或环境变量 PORT)")
    ap.add_argument("--host", default=None, help="监听地址,默认 127.0.0.1")
    ap.add_argument("--public", action="store_true", help="公网模式:绑定 0.0.0.0,写接口必须带访问口令")
    ap.add_argument("--lan", action="store_true", help="局域网模式:绑定 0.0.0.0,供同一 Wi-Fi 下手机访问")
    ap.add_argument("--token", default=None, help="访问口令,也可用环境变量 COLLECT_TOKEN")
    ap.add_argument("--api-only", action="store_true", help="采集端专用模式:只提供接口与采集页")
    args = ap.parse_args()

    if args.port:
        port = args.port
    elif args.port_pos and args.port_pos.isdigit():
        port = int(args.port_pos)
    else:
        port = int(os.environ.get("PORT", 8765))

    API_ONLY = args.api_only or (os.environ.get("SERVER_ROLE") or "").strip().lower() in ("api", "api-only", "collect")
    PUBLIC_MODE = bool(args.public)
    TOKEN = (args.token or os.environ.get("COLLECT_TOKEN") or "").strip()
    if PUBLIC_MODE and not TOKEN:
        print("错误:--public 公网模式必须提供访问口令(用 --token 或设置 COLLECT_TOKEN)", file=sys.stderr)
        sys.exit(2)

    host = args.host or ("0.0.0.0" if (PUBLIC_MODE or args.lan) else "127.0.0.1")
    if host not in ("127.0.0.1", "localhost") and not PUBLIC_MODE and not TOKEN:
        print("提示:当前监听了非本机地址但未设口令,写接口对本网段开放;需要对外请改用 --public --token",
              file=sys.stderr)

    with ReusableTCPServer((host, port), Handler) as httpd:
        role = "采集端专用(api-only)" if API_ONLY else "全功能(静态+接口)"
        mode = "公网+口令" if PUBLIC_MODE else ("局域网" if args.lan else ("口令" if TOKEN else "本机无口令"))
        print("采集服务已启动 [%s / %s]:" % (role, mode))
        print("  http://%s:%d/collect.html" % (host, port))
        if not API_ONLY:
            print("  http://%s:%d/index.html" % (host, port))
            print("  http://%s:%d/collector/settings.html" % (host, port))
            if args.lan and host == "0.0.0.0":
                addr = lan_ip()
                if addr:
                    print("局域网访问(手机与电脑需同一 Wi-Fi):")
                    print("  http://%s:%d/collector/settings.html" % (addr, port))
                else:
                    print("未自动识别局域网 IP,请用系统网络设置里的本机 IP 拼出访问地址")
        print("数据目录: %s" % generate.DATA_DIR)
        print("采集单元目录: %s" % generate.COLLECTIONS_DIR)
        if PUBLIC_MODE:
            print("写接口需在请求头带 X-Collect-Token(采集页顶部填入口令即可)")
        print("按 Ctrl+C 停止")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止")


if __name__ == "__main__":
    main()
