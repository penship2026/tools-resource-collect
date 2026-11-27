#!/usr/bin/env python3
"""二期 A0 截图矩阵:本机 Chrome/CDP，输出三档尺寸、溢出、dHash、结构指纹。

用法:
  python3 scripts/shot_matrix.py --baseline
  python3 scripts/shot_matrix.py --check
只依赖标准库 + Pillow；不安装 Playwright，不访问外网。
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "preview.html"
BASELINE = ROOT / "tests" / "baselines" / "p2-preview.json"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
LAYOUTS = ("standard", "news", "magazine")
THEMES = ("default", "dark", "tech", "campus", "classical")
SIZES = ((1280, 900), (768, 900), (390, 844))


def dhash(image: Image.Image) -> str:
    gray = ImageOps.grayscale(image).resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    bits = []
    for y in range(8):
        row = y * 9
        for x in range(8):
            bits.append("1" if pixels[row + x] > pixels[row + x + 1] else "0")
    return "".join(bits)


class WS:
    """最小 WebSocket 客户端，只服务 Chrome CDP 的本地 JSON 帧。"""

    def __init__(self, url: str):
        assert url.startswith("ws://")
        hostport, path = url[5:].split("/", 1)
        host, port = hostport.split(":")
        self.sock = socket.create_connection((host, int(port)), timeout=15)
        self.sock.settimeout(20)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.sock.recv(4096)
        if b"101" not in buf.split(b"\r\n", 1)[0]:
            raise RuntimeError("CDP websocket handshake failed")

    def send(self, text: str) -> None:
        payload = text.encode()
        header = bytearray([0x81])
        n = len(payload)
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header.extend(n.to_bytes(2, "big"))
        else:
            header.append(0x80 | 127)
            header.extend(n.to_bytes(8, "big"))
        mask = os.urandom(4)
        header.extend(mask)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(bytes(header) + masked)

    def _recv_exact(self, n: int) -> bytes:
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise RuntimeError("CDP connection closed")
            data += chunk
        return data

    def recv(self) -> str:
        chunks = []
        while True:
            first = self._recv_exact(2)
            fin = bool(first[0] & 0x80)
            opcode = first[0] & 0x0F
            n = first[1] & 0x7F
            if n == 126:
                n = int.from_bytes(self._recv_exact(2), "big")
            elif n == 127:
                n = int.from_bytes(self._recv_exact(8), "big")
            if first[1] & 0x80:
                mask = self._recv_exact(4)
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(self._recv_exact(n)))
            else:
                payload = self._recv_exact(n)
            if opcode == 0x8:
                raise RuntimeError("CDP websocket closed")
            if opcode == 0x9:
                # ping -> pong
                self.send_raw(payload, 0x8A)
                continue
            chunks.append(payload)
            if fin:
                return b"".join(chunks).decode()

    def send_raw(self, payload: bytes, opcode: int) -> None:
        header = bytearray([0x80 | opcode])
        n = len(payload)
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header.extend(n.to_bytes(2, "big"))
        else:
            header.append(0x80 | 127)
            header.extend(n.to_bytes(8, "big"))
        mask = os.urandom(4)
        header.extend(mask)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(bytes(header) + masked)

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


class CDP:
    def __init__(self):
        self._id = 0
        self._start()
        self.ws = WS(self.page_url)

    def _start(self):
        if not os.path.exists(CHROME):
            raise RuntimeError("找不到 Chrome:%s" % CHROME)
        port = self._free_port()
        self.profile = tempfile.mkdtemp(prefix="jiye-shot-")
        self.proc = subprocess.Popen([
            CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
            "--no-default-browser-check", "--allow-file-access-from-files",
            "--remote-debugging-port=%d" % port, "--user-data-dir=" + self.profile,
            "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        base = "http://127.0.0.1:%d" % port
        for _ in range(60):
            try:
                data = json.loads(urllib.request.urlopen(base + "/json/list", timeout=2).read())
                pages = [p for p in data if p.get("type") == "page"]
                if pages and pages[0].get("webSocketDebuggerUrl"):
                    self.page_url = pages[0]["webSocketDebuggerUrl"]
                    return
            except Exception:
                time.sleep(0.2)
        raise RuntimeError("Chrome CDP 未就绪")

    @staticmethod
    def _free_port() -> int:
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        return port

    def call(self, method: str, params=None) -> dict:
        self._id += 1
        self.ws.send(json.dumps({"id": self._id, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self._id:
                if "error" in msg:
                    raise RuntimeError("%s: %s" % (method, msg["error"]))
                return msg.get("result", {})

    def eval(self, expression: str):
        r = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
        return r.get("result", {}).get("value")

    def shot(self, url: str, width: int, height: int) -> dict:
        self.call("Emulation.setDeviceMetricsOverride", {
            "width": width, "height": height, "deviceScaleFactor": 1, "mobile": width <= 420,
        })
        self.call("Page.navigate", {"url": url})
        time.sleep(0.55)
        metrics = structure = None
        for _ in range(4):
            metrics = self.eval("""(() => {
              const d = document.documentElement, b = document.body;
              return {
                viewport: window.innerWidth,
                scrollWidth: Math.max(d.scrollWidth, b.scrollWidth),
                overflowX: Math.max(d.scrollWidth, b.scrollWidth) - d.clientWidth,
                layout: d.getAttribute('data-layout'),
                theme: d.getAttribute('data-theme')
              };
            })()""")
            if isinstance(metrics, dict):
                break
            time.sleep(0.2)
        if not isinstance(metrics, dict):
            raise RuntimeError("页面指标读取失败:%s" % url)
        structure = self.eval("""(() => {
          const tags = {}, classes = {};
          document.querySelectorAll('*').forEach(el => {
            const t = el.tagName.toLowerCase();
            tags[t] = (tags[t] || 0) + 1;
            el.classList.forEach(c => { classes[c] = (classes[c] || 0) + 1; });
          });
          return {tags, classes};
        })()""") or {}
        png = self.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})["data"]
        raw = base64.b64decode(png)
        image = Image.open(io.BytesIO(raw))
        return {
            "width": width, "height": height,
            "overflow_x": int(metrics.get("overflowX") or 0),
            "scroll_width": int(metrics.get("scrollWidth") or 0),
            "layout": metrics.get("layout"),
            "theme": metrics.get("theme"),
            "dhash": dhash(image),
            "image_sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "structure": structure,
        }

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass


def build_matrix() -> list[dict]:
    shots = []
    for layout in LAYOUTS:
        for theme in THEMES:
            for width, height in SIZES:
                url = FIXTURE.as_uri() + "?layout=%s&theme=%s" % (layout, theme)
                shots.append({"layout": layout, "theme": theme, "width": width, "height": height, "url": url})
    return shots


def hamming(a: str, b: str) -> int:
    return sum(1 for x, y in zip(a, b) if x != y) + abs(len(a) - len(b))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", action="store_true", help="重新生成基线 JSON")
    ap.add_argument("--check", action="store_true", help="与现有基线比对")
    args = ap.parse_args()
    if not args.baseline and not args.check:
        args.baseline = True
    cdp = CDP()
    rows = []
    try:
        for item in build_matrix():
            row = cdp.shot(item["url"], item["width"], item["height"])
            row.update({"layout": item["layout"], "theme": item["theme"]})
            rows.append(row)
            print("%-9s %-9s %4d  overflow=%d  %s" % (
                item["layout"], item["theme"], item["width"], row["overflow_x"], row["dhash"]))
    finally:
        cdp.close()

    payload = {
        "version": 1,
        "fixture": str(FIXTURE.relative_to(ROOT)),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "shots": rows,
    }
    BASELINE.parent.mkdir(parents=True, exist_ok=True)

    if args.check:
        if not BASELINE.exists():
            print("基线不存在:%s" % BASELINE, file=sys.stderr)
            return 1
        old = json.loads(BASELINE.read_text(encoding="utf-8"))
        old_map = {(r["layout"], r["theme"], r["width"]): r for r in old.get("shots", [])}
        bad = 0
        for row in rows:
            key = (row["layout"], row["theme"], row["width"])
            base = old_map.get(key)
            if not base:
                print("缺基线:%s" % (key,), file=sys.stderr)
                bad += 1
            elif row["overflow_x"] > 0:
                print("横向溢出:%s +%dpx" % (key, row["overflow_x"]), file=sys.stderr)
                bad += 1
            elif hamming(row["dhash"], base.get("dhash", "")) > 4:
                print("视觉漂移:%s (dHash 差 %d bit)" % (
                    key, hamming(row["dhash"], base.get("dhash", ""))), file=sys.stderr)
                bad += 1
            elif row.get("structure") != base.get("structure"):
                print("结构漂移:%s" % (key,), file=sys.stderr)
                bad += 1
        if bad:
            print("基线检查失败:%d 项" % bad, file=sys.stderr)
            return 1
        print("基线检查通过:%d 张" % len(rows))
        return 0

    BASELINE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("基线已写入:%s (%d 张)" % (BASELINE.relative_to(ROOT), len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
