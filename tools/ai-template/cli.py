#!/usr/bin/env python3
"""AI 设计编译器 CLI。

用法:
  python3 tools/ai-template/cli.py compile --spec tests/fixtures/specs/layout-news-dense.json
  python3 tools/ai-template/cli.py compile --spec tests/fixtures/specs/theme-mist.json --out /tmp/ai-theme
  python3 tools/ai-template/cli.py validate --spec ...
  python3 tools/ai-template/cli.py lint --file /tmp/ai-theme/mist.css
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

import compiler  # noqa: E402
import theme_lint  # noqa: E402


def _load(path):
    try:
        return compiler.load_json(path)
    except FileNotFoundError:
        print("找不到 Spec:%s" % path, file=sys.stderr)
        raise SystemExit(2)
    except json.JSONDecodeError as exc:
        print("Spec 不是合法 JSON:%s" % exc, file=sys.stderr)
        raise SystemExit(2)


def cmd_validate(args):
    spec = _load(args.spec)
    kind = args.kind or spec.get("kind")
    errors = compiler.validate_layout_spec(spec) if kind == "layout" else compiler.validate_theme_spec(spec)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"ok": True, "kind": kind, "key": spec.get("key")}, ensure_ascii=False))
    return 0


def cmd_compile(args):
    spec = _load(args.spec)
    kind = args.kind or spec.get("kind")
    try:
        result = compiler.compile_spec(
            spec, kind=kind, no_timestamp=not args.timestamp,
            approval=args.approval,
            timestamp=compiler.now_iso() if args.timestamp else None,
        )
    except compiler.SpecError as exc:
        print(json.dumps({"ok": False, "errors": exc.errors}, ensure_ascii=False, indent=2))
        return 1
    if kind == "theme":
        errors = theme_lint.lint_theme_css(result["css"])
        if errors:
            print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
            return 1
    out = Path(args.out) if args.out else HERE / "drafts" / spec["key"]
    out.mkdir(parents=True, exist_ok=True)
    css_path = out / ("%s.css" % spec["key"])
    reg_path = out / ("%s.registry.json" % spec["key"])
    css_path.write_text(result["css"], encoding="utf-8")
    reg_path.write_text(json.dumps(result["registry"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.print:
        print(result["css"])
    print(json.dumps({
        "ok": True, "kind": kind, "key": spec["key"],
        "css": str(css_path), "registry": str(reg_path),
        "bytes": len(result["css"].encode("utf-8")),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_lint(args):
    path = Path(args.file)
    errors = theme_lint.lint_theme_file(path)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"ok": True, "file": str(path)}, ensure_ascii=False))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="集页 AI 版式/主题编译器")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, handler in (("validate", cmd_validate), ("compile", cmd_compile), ("lint", cmd_lint)):
        p = sub.add_parser(name)
        if name != "lint":
            p.add_argument("--spec", required=True, help="Spec JSON 路径")
            p.add_argument("--kind", choices=("layout", "theme"), help="默认读取 spec.kind")
        if name == "compile":
            p.add_argument("--out", help="输出目录；默认 tools/ai-template/drafts/<key>")
            p.add_argument("--timestamp", action="store_true", help="写入生成时间；默认不写以保证可复现")
            p.add_argument("--approval", default="", help="审批号，写入注释")
            p.add_argument("--print", action="store_true", help="同时把 CSS 打到 stdout")
        if name == "lint":
            p.add_argument("--file", required=True, help="主题 CSS 路径")
        p.set_defaults(func=handler)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
