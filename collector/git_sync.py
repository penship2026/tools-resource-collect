#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设置页的 Git 数据同步：只提交采集数据，不碰代码/配置/文档。

固定仓库根、remote=origin、branch=main；不做 force / reset / clean。
所有外部命令用 subprocess.run([...], shell=False)。
"""

import os
import re
import subprocess

import generate


REMOTE = "origin"
BRANCH = "main"
DATA_INDEX = "assets/data/index.js"
DATA_PREFIX = "assets/data/collections/"
COMMIT_PREFIX = "data: 本机采集同步 "


class GitError(Exception):
    pass


def _git(args, timeout=30, check=False):
    proc = subprocess.run(
        ["git"] + list(args),
        cwd=generate.ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if check and proc.returncode != 0:
        raise GitError((proc.stderr or proc.stdout or "git 命令失败").strip())
    return proc


def _repo():
    git_path = os.path.join(generate.ROOT, ".git")
    return os.path.exists(git_path)


def _branch():
    proc = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _identity():
    name = _git(["config", "user.name"]).stdout.strip()
    email = _git(["config", "user.email"]).stdout.strip()
    return name, email


def _in_progress():
    git_dir = _git(["rev-parse", "--git-dir"]).stdout.strip() or ".git"
    if not os.path.isabs(git_dir):
        git_dir = os.path.join(generate.ROOT, git_dir)
    for name in ("MERGE_HEAD", "rebase-merge", "rebase-apply", "CHERRY_PICK_HEAD"):
        if os.path.exists(os.path.join(git_dir, name)):
            return name
    return ""


def _porcelain():
    proc = _git(["status", "--porcelain", "--untracked-files=all"])
    if proc.returncode != 0:
        raise GitError(proc.stderr.strip() or "git status 失败")
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    changes = []
    for line in lines:
        code, path = line[:2], line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        changes.append({"code": code, "path": path})
    return changes


def _allowed(path):
    return path == DATA_INDEX or (path.startswith(DATA_PREFIX) and path.endswith(".js"))


def _data_changes():
    changes = _porcelain()
    allowed = [c for c in changes if _allowed(c["path"])]
    blocked = [c for c in changes if not _allowed(c["path"])]
    deleted = [c for c in allowed if "D" in c["code"]]
    return allowed, blocked, deleted


def _remote_ahead():
    proc = _git(["rev-parse", "--verify", "origin/main"])
    if proc.returncode != 0:
        return False, "远端 origin/main 不存在"
    proc = _git(["merge-base", "--is-ancestor", "origin/main", "HEAD"])
    if proc.returncode == 0:
        return False, ""
    return True, "本地落后 origin/main，需人工 pull --rebase"


def status():
    if not _repo():
        return {"ok": False, "error": "GIT_NOT_REPO", "message": "项目根不是 Git 仓库"}
    branch = _branch()
    name, email = _identity()
    changes = _porcelain()
    ahead = behind = 0
    proc = _git(["rev-list", "--left-right", "--count", "HEAD...origin/main"])
    if proc.returncode == 0:
        parts = proc.stdout.split()
        if len(parts) == 2:
            ahead, behind = int(parts[0]), int(parts[1])
    return {
        "ok": True,
        "branch": branch,
        "ahead": ahead,
        "behind": behind,
        "changes": changes,
        "identity": {"name": name, "email": email},
        "dirty": bool(changes),
    }


def preview():
    if not _repo():
        return {"ok": False, "error": "GIT_NOT_REPO", "blockers": ["项目根不是 Git 仓库"]}
    st = status()
    blockers = []
    if st["branch"] != BRANCH:
        blockers.append("当前分支是 %s，必须切到 %s" % (st["branch"], BRANCH))
    if _in_progress():
        blockers.append("仓库处于合并/变基/拣选状态：%s" % _in_progress())
    if not (st["identity"]["name"] and st["identity"]["email"]):
        blockers.append("Git 身份缺失：请先配置 user.name / user.email")
    allowed, blocked, deleted = _data_changes()
    if deleted:
        blockers.append("白名单内存在删除文件，禁止提交：%s" % ", ".join(c["path"] for c in deleted))
    if not allowed:
        blockers.append("没有待提交的数据变更")
    # 白名单外变更不阻止推送：只提交 allowed 文件，代码/文档改动留在工作区
    remote_ahead, reason = _remote_ahead()
    if remote_ahead:
        blockers.append(reason)
    units = []
    items = 0
    for change in allowed:
        if change["path"] == DATA_INDEX:
            continue
        uid = os.path.basename(change["path"])[:-3]
        if uid not in units:
            units.append(uid)
            data = generate.load_collection_data(uid)
            if data:
                items += len(data.get("videos") or [])
    return {
        "ok": True,
        "branch": st["branch"],
        "files": [c["path"] for c in allowed],
        "units": len(units),
        "items": items,
        "blockers": blockers,
        "blocked_changes": [c["path"] for c in blocked],
        "remote_ahead": remote_ahead,
    }


def push():
    """执行预检 → fetch → verify → commit → push。返回结果字典，不抛异常。"""
    pv = preview()
    if not pv.get("ok") or pv.get("blockers"):
        return {"ok": False, "state": "blocked", "error": "GIT_PRECHECK_FAILED",
                "blockers": pv.get("blockers") or [pv.get("error", "预检失败")]}
    logs = []
    def log(msg):
        logs.append(str(msg))

    try:
        log("fetch origin main")
        _git(["fetch", REMOTE, BRANCH], timeout=60, check=True)
        remote_ahead, reason = _remote_ahead()
        if remote_ahead:
            return {"ok": False, "state": "blocked", "error": "GIT_REMOTE_AHEAD",
                    "blockers": [reason], "logs": logs}
        log("verify data")
        verify = generate.verify_data(log=log)
        if not verify["ok"]:
            return {"ok": False, "state": "blocked", "error": "VALIDATION_ERROR",
                    "blockers": verify["problems"], "logs": logs}
        allowed, blocked, deleted = _data_changes()
        if deleted:
            return {"ok": False, "state": "blocked", "error": "VALIDATION_ERROR",
                    "blockers": ["白名单内存在删除"], "logs": logs}
        files = [c["path"] for c in allowed]
        if not files:
            return {"ok": False, "state": "blocked", "error": "NO_CHANGES",
                    "blockers": ["没有待提交的数据变更"], "logs": logs}
        log("commit %d files" % len(files))
        _git(["add", "--"] + files, check=True)
        units = len({os.path.basename(p)[:-3] for p in files if p.startswith(DATA_PREFIX)})
        items = sum(len((generate.load_collection_data(os.path.basename(p)[:-3]) or {}).get("videos") or [])
                    for p in files if p.startswith(DATA_PREFIX))
        msg = "%s%s（%d 单元 / %d 条）" % (
            COMMIT_PREFIX, generate.now_stamp(), units, items)
        _git(["commit", "-m", msg], check=True)
        head = _git(["rev-parse", "HEAD"]).stdout.strip()
        log("push origin main")
        proc = _git(["-c", "http.version=HTTP/1.1", "push", REMOTE, BRANCH], timeout=120)
        if proc.returncode != 0:
            # 超时/网络失败后先用 ls-remote 判断是否其实已推上去，避免重复提交
            ls = _git(["ls-remote", REMOTE, BRANCH], timeout=30)
            remote = (ls.stdout.split()[0] if ls.stdout.split() else "")
            if remote == head:
                return {"ok": True, "state": "success", "commit": head, "files": len(files),
                        "units": units, "items": items, "logs": logs}
            return {"ok": False, "state": "committed_not_pushed", "error": "GIT_PUSH_FAILED",
                    "commit": head, "blockers": [(proc.stderr or proc.stdout).strip()],
                    "logs": logs}
        return {"ok": True, "state": "success", "commit": head, "files": len(files),
                "units": units, "items": items, "logs": logs}
    except subprocess.TimeoutExpired:
        return {"ok": False, "state": "failed", "error": "GIT_TIMEOUT",
                "blockers": ["Git 命令超时，请查看日志"], "logs": logs}
    except GitError as exc:
        return {"ok": False, "state": "failed", "error": "GIT_FAILED",
                "blockers": [str(exc)], "logs": logs}


def commit_is_remote(head):
    proc = _git(["ls-remote", REMOTE, BRANCH], timeout=30)
    remote = proc.stdout.split()[0] if proc.stdout.split() else ""
    return bool(remote) and remote == head
