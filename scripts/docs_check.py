#!/usr/bin/env python3
"""文档一致性自检(D38):只读,不改任何文件。

检查项:
  1. 关键文档存在(README / DEPLOY / GITHUB-PAGES / TODO / WORKLOG / PLAN / REVIEW)
  2. 口径统一:不再出现「四个页面」「三个页面」等旧说法
  3. 文档里提到的 docs/*.md 与仓库内文件对得上(不引用不存在的文档)
  4. workflow 引用的清单/脚本存在,且不内嵌重复的采集命令
  5. DEPLOY 覆盖本机 launchd 与「形态 A/B」
  6. 两套内置主题 token 完全对齐(D25/D31)
退出码:0 通过,1 有问题。
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED = [
    "README.md",
    "docs/DEPLOY.md",
    "docs/GITHUB-PAGES.md",
    "docs/TODO.md",
    "docs/WORKLOG.md",
    "docs/PLAN-20261126.md",
    "docs/REVIEW-20261126.md",
    "topics.yml",
    ".github/workflows/update-data.yml",
    "scripts/launchd/collect.sh",
]

STALE_PHRASES = ["四个页面", "三个页面", "四个静态页面", "三个静态页面"]

problems = []


def check_required():
    for rel in REQUIRED:
        if not os.path.exists(os.path.join(ROOT, rel)):
            problems.append("缺少文件: %s" % rel)


def doc_texts():
    out = {}
    for rel in REQUIRED:
        if rel.endswith(".md"):
            path = os.path.join(ROOT, rel)
            if os.path.exists(path):
                out[rel] = open(path, encoding="utf-8").read()
    return out


# REVIEW 是冻结的决策记录(见 PLAN 第八章),不参与口径检查
FROZEN = {"docs/REVIEW-20261126.md"}


def check_wording(texts):
    for rel, text in texts.items():
        if rel in FROZEN:
            continue
        for phrase in STALE_PHRASES:
            if phrase in text:
                problems.append("%s: 出现旧口径「%s」,统一为「五个页面」" % (rel, phrase))


def check_doc_links(texts):
    for rel, text in texts.items():
        for name in re.findall(r"docs/[A-Za-z0-9_.\-]+\.md", text):
            if "YYYY" in name:  # 模板里的占位名
                continue
            if not os.path.exists(os.path.join(ROOT, name)):
                problems.append("%s: 引用了不存在的文档 %s" % (rel, name))


def check_workflow():
    path = os.path.join(ROOT, ".github/workflows/update-data.yml")
    if not os.path.exists(path):
        return
    text = open(path, encoding="utf-8").read()
    # 清单外置:采集命令应通过 --topics 读清单,而不是逐个 --id 写死
    if "--topics" not in text:
        problems.append("update-data.yml: 未通过 --topics 读取主题清单")
    if re.search(r"generate\.py\s+.*--id", text):
        problems.append("update-data.yml: 仍在 workflow 里写死单个 --id,应改为 topics.yml")
    for name in re.findall(r"topics[.\w]*\.yml", text):
        if not os.path.exists(os.path.join(ROOT, name)):
            problems.append("update-data.yml: 引用的清单不存在 %s" % name)


THEME_TOKEN = re.compile(r"--[a-z0-9-]+\s*:")


def check_themes():
    """主题契约(D25/D31):两套内置主题的 token 必须完全对齐,避免「半套主题」。"""
    base = os.path.join(ROOT, "assets/themes")
    files = {"default.css": None, "dark.css": None}
    for name in files:
        path = os.path.join(base, name)
        if not os.path.exists(path):
            problems.append("缺少主题文件: assets/themes/%s" % name)
            continue
        text = open(path, encoding="utf-8").read()
        files[name] = set(m.group(0).rstrip(": ").strip() for m in THEME_TOKEN.finditer(text))
    if all(files.values()):
        missing_dark = files["default.css"] - files["dark.css"]
        missing_light = files["dark.css"] - files["default.css"]
        for name in sorted(missing_dark):
            problems.append("dark.css 缺少 token %s(与 default.css 不一致)" % name)
        for name in sorted(missing_light):
            problems.append("default.css 缺少 token %s(与 dark.css 不一致)" % name)


def check_deploy():
    path = os.path.join(ROOT, "docs/DEPLOY.md")
    if not os.path.exists(path):
        return
    text = open(path, encoding="utf-8").read()
    for need in ["形态 A", "launchd", "topics.yml"]:
        if need not in text:
            problems.append("DEPLOY.md: 缺少「%s」相关说明" % need)


def main():
    check_required()
    texts = doc_texts()
    check_wording(texts)
    check_doc_links(texts)
    check_workflow()
    check_themes()
    check_deploy()
    for p in problems:
        print("  ✗ %s" % p)
    print("文档自检%s(检查 %d 项)" % ("通过" if not problems else "未通过", len(problems)))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
