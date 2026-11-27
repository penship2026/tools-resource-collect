#!/usr/bin/env python3
"""A0 容量检查:5 套版式 + 5 套主题在 390px 必须用下拉且无横向溢出。"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from shot_matrix import CDP  # noqa: E402


def main() -> int:
    cdp = CDP()
    try:
        cdp.call("Emulation.setDeviceMetricsOverride", {
            "width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
        cdp.call("Page.navigate", {"url": (ROOT / "tests/fixtures/switch-5.html").as_uri()})
        time.sleep(0.6)
        result = cdp.eval("""(() => {
          const d = document.documentElement, b = document.body;
          return {
            overflow: Math.max(d.scrollWidth, b.scrollWidth) - d.clientWidth,
            layoutSelect: !!document.querySelector('.layout-select'),
            themeSelect: !!document.querySelector('.theme-select'),
            buttons: document.querySelectorAll('.layout-btn, .theme-btn').length
          };
        })()""")
    finally:
        cdp.close()
    print(result)
    if result.get("overflow", 0) > 0:
        print("失败:390px 横向溢出", file=sys.stderr)
        return 1
    if not result.get("layoutSelect") or not result.get("themeSelect"):
        print("失败:5 套未切换为下拉", file=sys.stderr)
        return 1
    if result.get("buttons"):
        print("失败:5 套仍渲染按钮", file=sys.stderr)
        return 1
    print("5+5 容量检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
