#!/usr/bin/env python3
"""本地静态展示站服务器。

只做一件事：为 index.html / assets/ 提供本地预览。所有响应都加 no-store，
避免采集更新 index.js 后，浏览器继续用旧缓存导致新单元“进不了首页列表”。
"""
import argparse
import http.server
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, fmt, *args):
        super().log_message(fmt, *args)


def main():
    parser = argparse.ArgumentParser(description="本地静态展示站（禁止浏览器缓存数据）")
    parser.add_argument("--port", type=int, default=int(os.environ.get("WEB_PORT", "8000")))
    parser.add_argument("--bind", default="127.0.0.1", help="默认只绑定本机")
    args = parser.parse_args()
    server = http.server.ThreadingHTTPServer((args.bind, args.port), Handler)
    print("网站服务已启动: http://%s:%d/" % (args.bind, args.port))
    print("按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
