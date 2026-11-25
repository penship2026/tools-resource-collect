#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
采集数据备份 / 还原工具(纯 Python 标准库)

数据边界 = 采集产出(采集只写数据,页面是固定模板不随采集变化):
  assets/data/index.js                  采集单元索引(含显示开关)
  assets/data/collections/<id>.js       每次采集的独立数据
三个页面(index.html / series.html / single.html)、样式和程序本身不纳入备份,
它们不随采集变化,随代码版本管理即可。

用法:
  python3 backup_data.py backup               # 打包当前数据到 backups/,带时间戳
  python3 backup_data.py list                 # 列出已有备份
  python3 backup_data.py restore <备份文件>    # 还原(默认先备份现状,再覆盖)
  python3 backup_data.py restore <备份文件> --yes   # 跳过确认(用于脚本)
  python3 backup_data.py backup --out /path    # 指定备份存放目录

可选环境变量(与 generate.py / server.py 一致,便于分离部署时指向共享目录):
  VIDEO_DATA_DIR    数据目录,默认 assets/data
  VIDEO_BACKUP_DIR  备份存放目录,默认 backups

还原安全:仅解包 *.js 到目标目录,拒绝 .. 路径穿越与绝对路径,避免误覆盖其他文件。
"""

import argparse
import datetime
import os
import shutil
import sys
import zipfile

# 本脚本位于 <项目根>/collector/,项目根是它的父目录(可用 VIDEO_PROJECT_ROOT 覆盖)。
# 备份包内的归档路径以项目根为基准,因此 ROOT 必须指向项目根。
ROOT = (os.environ.get("VIDEO_PROJECT_ROOT") or "").strip() or \
       os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.abspath(ROOT)


def _resolve_dir(env_name, default_rel):
    value = (os.environ.get(env_name) or "").strip()
    if not value:
        return os.path.join(ROOT, default_rel)
    return value if os.path.isabs(value) else os.path.join(ROOT, value)


DATA_DIR = _resolve_dir("VIDEO_DATA_DIR", os.path.join("assets", "data"))
COLLECTIONS_DIR = os.path.join(DATA_DIR, "collections")
BACKUP_DIR = _resolve_dir("VIDEO_BACKUP_DIR", "backups")

# 归档内相对路径前缀(相对"数据根目录"的上层,即项目根)
INDEX_ARC = "assets/data/index.js"
COLLECTIONS_ARC = "assets/data/collections"


def _collect_files():
    """返回 [(归档内路径, 磁盘绝对路径)] 列表:索引 + 各采集单元数据"""
    items = []
    index_path = os.path.join(DATA_DIR, "index.js")
    if os.path.isfile(index_path):
        items.append((INDEX_ARC, index_path))
    if os.path.isdir(COLLECTIONS_DIR):
        for name in sorted(os.listdir(COLLECTIONS_DIR)):
            full = os.path.join(COLLECTIONS_DIR, name)
            if os.path.isfile(full) and name.lower().endswith(".js"):
                items.append(("%s/%s" % (COLLECTIONS_ARC, name), full))
    return items


def cmd_backup(args):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    items = _collect_files()
    if not items:
        print("没有可备份的数据文件(数据目录为空或不存在)")
        return 1

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = os.path.abspath(args.out) if args.out else BACKUP_DIR
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "data-%s.zip" % stamp)

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for arc, full in items:
            zf.write(full, arc)
    print("备份完成: %s" % path)
    print("  索引文件: 1 个")
    print("  采集单元: %d 个,压缩包 %.1f KB" % (
        sum(1 for a, _ in items if a.startswith(COLLECTIONS_ARC)),
        os.path.getsize(path) / 1024.0))
    return 0


def cmd_list(args):
    if not os.path.isdir(BACKUP_DIR):
        print("暂无备份目录: %s" % BACKUP_DIR)
        return 0
    files = sorted(f for f in os.listdir(BACKUP_DIR) if f.endswith(".zip"))
    if not files:
        print("暂无备份")
        return 0
    print("备份目录: %s" % BACKUP_DIR)
    for f in files:
        full = os.path.join(BACKUP_DIR, f)
        size = os.path.getsize(full) / 1024.0
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(full))
        print("  %-28s %7.1f KB  %s" % (f, size, mtime.strftime("%Y-%m-%d %H:%M:%S")))
    return 0


def _safe_members(zf):
    """校验归档成员,返回可安全还原的 [(归档名, 目标绝对路径)]"""
    result = []
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if name.startswith("/") or ".." in name.split("/"):
            print("跳过不安全的归档路径: %s" % info.filename)
            continue
        if not name.lower().endswith(".js"):
            print("跳过非数据文件: %s" % info.filename)
            continue
        if name == INDEX_ARC:
            target = os.path.join(DATA_DIR, "index.js")
        elif name.startswith(COLLECTIONS_ARC + "/"):
            target = os.path.join(COLLECTIONS_DIR, name[len(COLLECTIONS_ARC) + 1:])
        else:
            print("跳过非数据文件: %s" % info.filename)
            continue
        result.append((name, target))
    return result


def cmd_restore(args):
    src = os.path.abspath(args.file)
    if not os.path.isfile(src):
        print("备份文件不存在: %s" % src)
        return 1

    with zipfile.ZipFile(src) as zf:
        members = _safe_members(zf)
        if not members:
            print("备份中没有可还原的数据文件")
            return 1
        print("将还原 %d 个文件到:" % len(members))
        print("  数据目录: %s" % DATA_DIR)
        print("  采集单元: %s" % COLLECTIONS_DIR)
        if not args.yes:
            try:
                answer = input("覆盖现有数据? [y/N] ").strip().lower()
            except EOFError:
                answer = ""
            if answer not in ("y", "yes"):
                print("已取消")
                return 0

        # 还原前自动留一份当前快照,避免误还原无法回退
        if not args.no_snapshot:
            os.makedirs(BACKUP_DIR, exist_ok=True)
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            snapshot = os.path.join(BACKUP_DIR, "before-restore-%s.zip" % stamp)
            with zipfile.ZipFile(snapshot, "w", zipfile.ZIP_DEFLATED) as szf:
                for arc, full in _collect_files():
                    szf.write(full, arc)
            print("已自动留存当前数据快照: %s" % snapshot)

        for name, target in members:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with zf.open(name) as r, open(target, "wb") as w:
                shutil.copyfileobj(r, w)
    print("还原完成")
    return 0


def build_parser():
    p = argparse.ArgumentParser(description="采集数据备份 / 还原工具")
    sub = p.add_subparsers(dest="cmd")

    b = sub.add_parser("backup", help="打包当前数据")
    b.add_argument("--out", help="备份存放目录(默认 backups,可用 VIDEO_BACKUP_DIR)")
    b.set_defaults(func=cmd_backup)

    sub.add_parser("list", help="列出已有备份").set_defaults(func=cmd_list)

    r = sub.add_parser("restore", help="从备份还原")
    r.add_argument("file", help="备份 zip 文件路径")
    r.add_argument("--yes", action="store_true", help="跳过确认")
    r.add_argument("--no-snapshot", action="store_true", help="还原前不自动留存当前快照")
    r.set_defaults(func=cmd_restore)
    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not getattr(args, "cmd", None):
        parser.print_help()
        return 0
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
