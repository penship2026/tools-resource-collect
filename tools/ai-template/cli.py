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
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

import compiler  # noqa: E402
import theme_lint  # noqa: E402


def _load_local(name, filename):
    """按文件路径加载，避免与仓库根同名模块冲突。"""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


generate = _load_local("ai_template_generate", "generate.py")
preview = _load_local("ai_template_preview", "preview.py")
publish = _load_local("ai_template_publish", "publish.py")
display = _load_local("ai_template_display", "display.py")
server = _load_local("ai_template_server", "server.py")


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


def cmd_generate(args):
    try:
        run = generate.generate(
            args.kind, args.request, constraints=args.constraints,
            mock=args.mock, out_dir=args.out, use_cache=not args.no_cache,
            attempts=args.attempts,
        )
    except generate.GenerationError as exc:
        print(json.dumps({"ok": False, "errors": exc.errors, "raw_tail": exc.raw[-400:]},
                         ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(run, ensure_ascii=False, indent=2))
    return 0


def cmd_preview(args):
    spec_path = Path(args.spec)
    try:
        spec = compiler.load_json(spec_path)
    except FileNotFoundError:
        print("找不到 Spec:%s" % spec_path, file=sys.stderr)
        return 1
    kind = args.kind or spec.get("kind")
    if kind not in ("layout", "theme"):
        print("Spec kind 无效:%s" % kind, file=sys.stderr)
        return 1
    out = Path(args.out) if args.out else spec_path.parent
    report = preview.evaluate(spec, kind, out, no_shot=args.no_shot, quick=args.quick)
    preview.metrics.write_report(out / "metrics.json", report)
    summary = {
        "ok": report["ok"],
        "key": report["key"],
        "visual": report.get("visual"),
        "errors": [{"gate": g["gate"], "code": g["code"], "message": g["message"]}
                   for g in report["gates"] if not g.get("ok")],
        "metrics": report.get("metrics"),
        "report": str(out / "metrics.json"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


def cmd_lint(args):
    path = Path(args.file)
    errors = theme_lint.lint_theme_file(path)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"ok": True, "file": str(path)}, ensure_ascii=False))
    return 0


def cmd_serve(args):
    server.serve(args.port, ROOT)
    return 0


def _print_result(result):
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


def cmd_approve(args):
    try:
        result = publish.approve_candidate(
            Path(args.spec), args.reviewer, root=ROOT, note=args.note,
            model=args.model, prompt_id=args.prompt_id, rounds=args.rounds,
        )
    except publish.PublishError as exc:
        return _print_result(exc.as_dict())
    return _print_result(result)


def cmd_reject(args):
    try:
        result = publish.reject_candidate(
            Path(args.spec), args.reviewer, args.reason, args.note, root=ROOT,
        )
    except publish.PublishError as exc:
        return _print_result(exc.as_dict())
    return _print_result(result)


def cmd_revise(args):
    try:
        result = publish.record_revision(Path(args.spec), args.comments, args.reviewer, root=ROOT)
    except publish.PublishError as exc:
        return _print_result(exc.as_dict())
    return _print_result(result)


def cmd_display(args):
    try:
        result = display.set_visible(args.kind, args.key, bool(args.on), root=ROOT)
    except display.DisplayError as exc:
        return _print_result(exc.as_dict())
    return _print_result(result)


def main(argv=None):
    ap = argparse.ArgumentParser(description="集页 AI 版式/主题编译器")
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name, handler in (("validate", cmd_validate), ("compile", cmd_compile)):
        p = sub.add_parser(name)
        p.add_argument("--spec", required=True, help="Spec JSON 路径")
        p.add_argument("--kind", choices=("layout", "theme"), help="默认读取 spec.kind")
        if name == "compile":
            p.add_argument("--out", help="输出目录；默认 tools/ai-template/drafts/<key>")
            p.add_argument("--timestamp", action="store_true", help="写入生成时间；默认不写以保证可复现")
            p.add_argument("--approval", default="", help="审批号，写入注释")
            p.add_argument("--print", action="store_true", help="同时把 CSS 打到 stdout")
        p.set_defaults(func=handler)

    p = sub.add_parser("generate", help="从自然语言生成 3 个候选草稿（默认离线 mock 降级）")
    p.add_argument("--kind", required=True, choices=("layout", "theme"))
    p.add_argument("--request", required=True, help="目标场景 / 设计需求")
    p.add_argument("--constraints", default="", help="额外约束")
    p.add_argument("--mock", action="store_true", help="强制离线 mock；无 AI_* 时自动降级")
    p.add_argument("--out", help="草稿根目录；默认 tools/ai-template/drafts")
    p.add_argument("--no-cache", action="store_true", help="不复用同 prompt 的缓存")
    p.add_argument("--attempts", type=int, default=2, help="JSON/schema 失败重试次数，默认 2")
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("preview", help="固定 fixture 预览 + 六道闸门")
    p.add_argument("--spec", required=True, help="候选 spec.json 路径")
    p.add_argument("--kind", choices=("layout", "theme"), help="默认读取 spec.kind")
    p.add_argument("--out", help="候选目录；默认 spec 所在目录")
    p.add_argument("--no-shot", action="store_true", help="只跑静态闸门，视觉标记 skipped")
    p.add_argument("--quick", action="store_true", help="只跑 default 主题，用于冒烟")
    p.set_defaults(func=cmd_preview)

    p = sub.add_parser("lint")
    p.add_argument("--file", required=True, help="主题 CSS 路径")
    p.set_defaults(func=cmd_lint)

    p = sub.add_parser("serve", help="启动 127.0.0.1 工作台（评审 + 管理处）")
    p.add_argument("--port", type=int, default=8787, help="默认 8787")
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("approve", help="批准候选并原子发布")
    p.add_argument("--spec", required=True, help="候选 spec.json 路径")
    p.add_argument("--reviewer", required=True, help="审批人，必填")
    p.add_argument("--note", default="", help="审批备注")
    p.add_argument("--model", default="", help="生成模型名，仅记录")
    p.add_argument("--prompt-id", default="generate-v1", help="prompt 版本，仅记录")
    p.add_argument("--rounds", type=int, default=1, help="迭代轮次，默认 1")
    p.set_defaults(func=cmd_approve)

    p = sub.add_parser("reject", help="驳回候选并留记录")
    p.add_argument("--spec", required=True, help="候选 spec.json 路径")
    p.add_argument("--reviewer", required=True, help="审批人，必填")
    p.add_argument("--reason", required=True, choices=("同质化", "破版", "观感差", "不支持该场景"))
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_reject)

    p = sub.add_parser("revise", help="记录迭代意见；超过 2 轮转人工")
    p.add_argument("--spec", required=True, help="候选 spec.json 路径")
    p.add_argument("--comments", required=True, help="迭代意见")
    p.add_argument("--reviewer", default="")
    p.set_defaults(func=cmd_revise)

    p = sub.add_parser("display", help="管理处上下架展示项")
    p.add_argument("--kind", required=True, choices=("layout", "theme"))
    p.add_argument("--key", required=True)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--on", action="store_true", help="上架")
    group.add_argument("--off", action="store_true", help="下架")
    p.set_defaults(func=cmd_display)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
