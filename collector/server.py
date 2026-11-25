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
  GET  /api/topics             列出已有主题
  GET  /*                      静态文件托管(首页/子页/数据)

运行角色(便于采集端与展示端分离部署,同机/同容器下共享数据目录):
  --api-only  采集端专用模式:只提供 /api/* 与 /collect.html,不再托管静态首页/子页,
             静态展示交给独立的 Web 服务器(如 Nginx)。默认(不带该参数)为全功能模式,
             向后兼容。也可用环境变量 SERVER_ROLE=api 指定。
说明: 接口路径支持带任意前缀(如部署在子路径 /app/ 下时 /app/api/collect 同样有效)。
"""

import http.server
import json
import os
import re
import socketserver
import sys
import urllib.parse

import generate

# 采集代码位于 <项目根>/collector/,展示页面与数据在项目根。
# ROOT 指向项目根用于静态托管;COLLECTOR_DIR 指向本目录用于定位采集页。
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = (os.environ.get("VIDEO_PROJECT_ROOT") or "").strip() or os.path.dirname(SCRIPT_DIR)
ROOT = os.path.abspath(ROOT)
COLLECTOR_DIR = SCRIPT_DIR

# 运行角色:full=静态+接口全托管(默认);api=仅接口+采集页(展示端由独立 Web 服务器提供)
API_ONLY = False


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def translate_path(self, path):
        # 兼容旧访问路径:/collect.html 现在实际位于 collector/collect.html。
        # 同时保留 /collector/collect.html 的自然路径。
        clean = (path or "").split("?", 1)[0].split("#", 1)[0]
        tail = clean.rstrip("/").split("/")[-1]
        if tail == "collect.html" and not clean.startswith("/collector/"):
            return os.path.join(COLLECTOR_DIR, "collect.html")
        return super().translate_path(path)

    def log_message(self, fmt, *args):
        # 只打印简单访问日志,避免刷屏
        if "/api/" in (self.path or ""):
            return
        super().log_message(fmt, *args)

    def end_headers(self):
        # 所有响应(含静态文件)统一禁用缓存:
        # 采集更新数据后,手机浏览器若缓存了 index.js 就会一直显示旧首页
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path.endswith("/api/health"):
            # 采集只写数据:数据目录 + 采集单元目录,两处都可写才算健康
            data_ok = os.access(generate.DATA_DIR, os.W_OK)
            coll_ok = os.access(generate.COLLECTIONS_DIR, os.W_OK)
            self._json({
                "ok": True,
                "writable": data_ok and coll_ok,
                "data_dir": generate.DATA_DIR,
                "collections_dir": generate.COLLECTIONS_DIR,
                "data_writable": data_ok,
                "collections_writable": coll_ok,
                "role": "api" if API_ONLY else "full",
            })
            return
        if path.endswith("/api/topics"):
            index = generate.load_index()
            self._json({"ok": True, "topics": [
                {
                    "id": t.get("id"),
                    "title": t.get("title"),
                    "type": t.get("type", "series"),
                    "enabled": t.get("enabled", True),
                    "count": t.get("count", 0),
                    "page": t.get("page"),
                    "author": (t.get("source") or {}).get("name", ""),
                    "keyword": t.get("keyword", ""),
                    "created": t.get("created", ""),
                    "updated": t.get("updated", ""),
                } for t in index
            ]})
            return
        # 未知 /api/ 路径一律返回 JSON,避免 Python 默认 HTML 404 让前端 json() 解析失败
        if "/api/" in path:
            self._json({"ok": False, "error": "未知接口: %s" % path}, 404)
            return
        # 采集端专用模式:只放行采集页本身和它依赖的样式表,其他静态文件由展示端 Web 服务器提供
        if API_ONLY:
            tail = path.rstrip("/").split("/")[-1]
            if tail in ("collect.html", "style.css"):
                return super().do_GET()
            self._json({
                "ok": False,
                "error": "当前为采集端专用模式(api-only),静态展示请访问独立的展示站服务",
                "hint": "采集页仍是 /collect.html",
            }, 404)
            return
        return super().do_GET()

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8") if length else "{}"
            payload = json.loads(body)
        except Exception as exc:
            self._json({"ok": False, "error": "请求参数错误: %s" % exc}, 400)
            return

        # 开启/关闭某采集单元的显示
        if path.endswith("/api/toggle"):
            unit_id = (payload.get("id") or "").strip()
            if not unit_id:
                self._json({"ok": False, "error": "缺少单元 id"}, 400)
                return
            enabled = bool(payload.get("enabled"))
            try:
                result = generate.set_enabled(unit_id, enabled)
            except Exception as exc:
                self._json({"ok": False, "error": "切换显示失败: %s" % exc}, 500)
                return
            self._json(result, 200 if result.get("ok") else 404)
            return

        if not path.endswith("/api/collect"):
            self._json({"ok": False, "error": "未知接口"}, 404)
            return

        keyword = (payload.get("keyword") or "").strip()
        mode = (payload.get("mode") or "keyword").strip()
        if not keyword:
            self._json({"ok": False, "error": "视频链接/BV 号不能为空" if mode == "url" else "主题关键词不能为空"}, 400)
            return

        # 收集日志,随响应返回给前端展示
        logs = []
        def log(msg):
            logs.append(str(msg))

        try:
            if mode == "url":
                result = generate.collect_by_url(
                    url=keyword,
                    title=(payload.get("title") or "").strip() or None,
                    unit_id=(payload.get("unit_id") or payload.get("slug") or "").strip() or None,
                    slogan=(payload.get("slogan") or "").strip() or None,
                    dry_run=bool(payload.get("dry_run")),
                    log=log,
                )
            else:
                result = generate.collect_topic(
                    keyword=keyword,
                    pages=int(payload.get("pages") or 30),
                    title=(payload.get("title") or "").strip() or None,
                    up=(payload.get("up") or "").strip() or None,
                    unit_id=(payload.get("unit_id") or payload.get("slug") or "").strip() or None,
                    slogan=(payload.get("slogan") or "").strip() or None,
                    min_match=int(payload.get("min_match") or 2),
                    match_all=bool(payload.get("match_all")),
                    dry_run=bool(payload.get("dry_run")),
                    log=log,
                )
        except Exception as exc:
            self._json({"ok": False, "error": "采集失败: %s" % exc, "logs": logs}, 500)
            return

        result["logs"] = logs
        self._json(result, 200 if result.get("ok") else 500)


# 允许端口复用:避免服务重启时因 TIME_WAIT/残留进程报 Address already in use
class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def main():
    global API_ONLY
    # 端口优先用命令行第一个数字参数,其次环境变量 PORT(部署平台常通过它注入),最后默认 8765
    args = [a for a in sys.argv[1:]]
    port_args = [a for a in args if a.isdigit()]
    port = int(port_args[0]) if port_args else int(os.environ.get("PORT", 8765))
    # 运行角色:命令行 --api-only 或环境变量 SERVER_ROLE=api
    API_ONLY = "--api-only" in args or (os.environ.get("SERVER_ROLE") or "").strip().lower() in ("api", "api-only", "collect")

    # 监听 0.0.0.0,否则部署后外部请求无法到达 Python 服务,会被静态托管接管返回 HTML
    with ReusableTCPServer(("0.0.0.0", port), Handler) as httpd:
        role = "采集端专用(api-only)" if API_ONLY else "全功能(静态+接口)"
        print("采集服务已启动 [%s]:" % role)
        print("  http://0.0.0.0:%d/collect.html" % port)
        if not API_ONLY:
            print("  http://0.0.0.0:%d/index.html" % port)
        print("数据目录: %s" % generate.DATA_DIR)
        print("采集单元目录: %s" % generate.COLLECTIONS_DIR)
        print("按 Ctrl+C 停止")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止")


if __name__ == "__main__":
    main()
