#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
神奇网站挖掘机 · 采集数据生成器

纯规则程序,不调用任何 AI:
  输入主题关键词 → 调用 B站 公开搜索 API → 按规则聚类同系列视频 → 写入一个采集单元的数据

采集只处理数据,不生成、不修改任何静态页面。页面是三个固定模板(index.html /
series.html / single.html),由人工单独维护布局样式,通过 ?id= 读取对应采集单元的数据。

数据架构:每次采集是一个独立单元,单独存一个数据文件,互不覆盖;重新采集命中
同一 id 时只更新该单元,可单独关闭某单元的显示。
  assets/data/index.js                  索引(各单元元信息 + 显示开关)
  assets/data/collections/<id>.js       该单元的视频数据

用法:
  python3 generate.py "每天挖掘一个神奇网站"            # 按主题采集(type=series)
  python3 generate.py "跟着动画学古文" --up "某个UP主"
  python3 generate.py "https://www.bilibili.com/video/BVxxx/" --url   # 按链接采集(type=single)
  python3 generate.py --id daily-website "新关键词"       # 重新采集指定单元,只更新它
  python3 generate.py --toggle daily-website --off        # 关闭某单元显示
  python3 generate.py --toggle daily-website --on         # 开启某单元显示
  python3 generate.py --list                              # 列出所有采集单元
  python3 generate.py --migrate                           # 从旧版 topic 数据迁移

可选参数:
  --url            按 B站 视频链接/BV 号采集单条视频(type=single)
  --id ID          指定采集单元 id;命中已有单元则只更新它,不新建
  --pages N        搜索翻页数,默认 30(每页 20 条)
  --title T        显示标题,默认等于关键词
  --up NAME        限定 UP 主名称,结果更精确
  --slug NAME      同 --id,兼容旧参数
  --slogan TEXT    副标题
  --dry-run        只预览不写文件

注意:关键词采用精准匹配,必须完整出现在视频标题中(可多字,但不拆分)。
"""

import argparse
import datetime
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import uuid

# 本脚本位于 <项目根>/collector/,项目根是它的父目录。
# 可用 VIDEO_PROJECT_ROOT 显式覆盖(例如把 collector 目录整体搬到别处时)。
# 数据与展示页面都在项目根下,ROOT 必须指向项目根,否则默认数据目录会错位。
ROOT = (os.environ.get("VIDEO_PROJECT_ROOT") or "").strip() or \
       os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.abspath(ROOT)
ASSETS = os.path.join(ROOT, "assets")

# 数据目录可通过环境变量覆盖,便于「采集端 / 展示端」分离部署时指向同一共享目录。
# 不设置时保持默认(assets/data 与 topics),页面相对路径引用完全不变。
# 相对路径按项目根 ROOT 解析,绝对路径直接使用。
def _resolve_dir(env_name, default_rel):
    value = (os.environ.get(env_name) or "").strip()
    if not value:
        return os.path.join(ROOT, default_rel)
    return value if os.path.isabs(value) else os.path.join(ROOT, value)


DATA_DIR = _resolve_dir("VIDEO_DATA_DIR", os.path.join("assets", "data"))
INDEX_JS = os.path.join(DATA_DIR, "index.js")
# 每次采集是独立单元,数据单独存一个文件,便于局部更新与单独关闭显示
COLLECTIONS_DIR = os.path.join(DATA_DIR, "collections")
# 旧版目录:迁移时读取,采集本身不再写入
LEGACY_DIR = _resolve_dir("VIDEO_TOPICS_DIR", "topics")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def clean_html(text):
    """去掉 B站 搜索结果标题中的 <em> 高亮标签"""
    return html.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


def make_headers():
    """B站 搜索 API 需要 buvid3 cookie,否则第二次请求会被风控拦截"""
    return {
        "User-Agent": UA,
        "Referer": "https://www.bilibili.com/",
        "Cookie": "buvid3=%sinfoc" % uuid.uuid4(),
        "Accept": "application/json, text/plain, */*",
    }


def search_bilibili(keyword, pages, verbose=True):
    """调用 B站 搜索 API 抓取多页结果(纯 HTTP,无浏览器,无 AI)"""
    items = []
    for page in range(1, pages + 1):
        params = urllib.parse.urlencode({
            "search_type": "video", "keyword": keyword, "page": page,
        })
        url = "https://api.bilibili.com/x/web-interface/search/type?" + params
        try:
            req = urllib.request.Request(url, headers=make_headers())
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            if verbose:
                print("  第 %d 页请求失败: %s" % (page, exc), file=sys.stderr)
            break
        if data.get("code") != 0:
            if verbose:
                print("  第 %d 页返回 code=%s,停止翻页" % (page, data.get("code")), file=sys.stderr)
            break
        result = data.get("data", {}).get("result", [])
        if not result:
            break
        items.extend(result)
        if verbose and page % 5 == 0:
            print("  已抓取 %d 页,累计 %d 条..." % (page, len(items)), file=sys.stderr)
        time.sleep(0.35)
    return items


def title_match(title, keyword, min_match=None, match_all=None):
    """
    精准匹配:关键词必须完整出现在标题中。
    允许标题比关键词多字(前后有别的词),但绝不把关键词拆成片段来匹配。
    例如关键词「每天挖掘一个神奇网站」可匹配
    「每天挖掘一个神奇网站：一个免费学英语的网站」,
    但不会匹配只含「神奇网站」或「动画学古文」碎片的内容。
    """
    if not keyword:
        return False
    return keyword in title


def pick_series(items, keyword, up_name, min_match, match_all):
    """
    纯统计规则聚类同系列:
      1. 按标题匹配筛候选
      2. 指定 --up 时按作者过滤(仍要求标题相关)
      3. 否则取候选中频次最高的 UP 主作为系列主账号
    """
    candidates = [
        x for x in items
        if title_match(clean_html(x.get("title", "")), keyword, min_match, match_all)
    ]
    if not candidates:
        return [], []

    if up_name:
        chosen = [
            x for x in candidates
            if x.get("author") == up_name
        ]
        return chosen, [(up_name, len(chosen))]

    counter = {}
    for x in candidates:
        author = x.get("author", "")
        counter[author] = counter.get(author, 0) + 1
    ranked = sorted(counter.items(), key=lambda kv: -kv[1])
    if not ranked:
        return [], []
    main_author = ranked[0][0]
    chosen = [x for x in candidates if x.get("author") == main_author]
    return chosen, ranked[:5]


def normalize(video, keyword=""):
    """把 API 字段转成站点需要的结构;播放链接只保留干净的 BV 地址"""
    title = clean_html(video.get("title", ""))
    if keyword and title.startswith(keyword):
        rest = title[len(keyword):].lstrip("：: ·—-")
        if rest:
            title = rest
    cover = video.get("pic", "") or ""
    if cover.startswith("//"):
        cover = "https:" + cover
    pub = video.get("pubdate", 0)
    # 日期带年份,避免往年数据(如 2024.01)与今年混淆;格式统一为 yyyy.mm.dd
    try:
        date = datetime.datetime.fromtimestamp(pub).strftime("%Y.%m.%d")
    except Exception:
        date = "—"
    # 干净的播放地址:B站官方 BV 播放页,不带任何追踪参数
    bv = video.get("bvid", "")
    # 简介:优先 description,其次 desc
    desc = clean_html(video.get("description") or video.get("desc") or "")
    return {
        "title": title,
        "bv": bv,
        "url": "https://www.bilibili.com/video/%s/" % bv,
        "cover": cover,
        "views": str(video.get("play", 0)),
        "date": date,
        "ts": pub,
        "author": video.get("author", ""),
        "desc": desc[:160],
    }


def slugify(keyword, slug_arg, existing_ids):
    """生成唯一且安全的文件名"""
    if slug_arg:
        base = re.sub(r"[^a-zA-Z0-9_-]", "", slug_arg)
        return base or "topic"
    digest = hashlib.md5(keyword.encode("utf-8")).hexdigest()[:8]
    base = "topic-" + digest
    while base in existing_ids:
        digest = hashlib.md5((digest + "x").encode()).hexdigest()[:8]
        base = "topic-" + digest
    return base


def js(value):
    """Python 值转 JS 字面量"""
    return json.dumps(value, ensure_ascii=False, indent=2)


def load_index():
    """读取采集单元索引,返回元信息列表(每个单元一条)"""
    if not os.path.exists(INDEX_JS):
        return []
    text = open(INDEX_JS, encoding="utf-8").read()
    # 优先读新格式 window.COLLECTION_INDEX,兼容 const 声明与旧格式 TOPIC_INDEX
    m = re.search(r"(?:window\.)?(?:const\s+)?(?:COLLECTION_INDEX|TOPIC_INDEX)\s*=\s*(\[.*\])\s*;", text, re.S)
    if not m:
        return []
    try:
        items = json.loads(m.group(1))
    except Exception as exc:
        print("  警告:读取采集索引失败: %s" % exc, file=sys.stderr)
        return []
    # 旧格式补齐默认字段,让页面与接口都能直接用
    for it in items:
        it.setdefault("type", "series")
        it.setdefault("enabled", True)
        it.setdefault("created", "")
        it.setdefault("updated", "")
    return items


def write_index(items, updated):
    """重写采集单元索引文件"""
    lines = [
        "// 采集单元索引,由 generate.py 自动生成",
        "// 挂到 window 上,页面中用 window.COLLECTION_INDEX 读取(const 不会挂到 window)",
        "window.SITE = {",
        "  name: %s," % json.dumps("神奇网站挖掘机 · 视频聚合站", ensure_ascii=False),
        "  description: %s," % json.dumps("按主题汇总各平台的神奇网站推荐视频,持续更新", ensure_ascii=False),
        "  updated: %s," % json.dumps(updated),
        "};",
        "window.COLLECTION_INDEX = %s;" % json.dumps(items, ensure_ascii=False, indent=2),
    ]
    with open(INDEX_JS, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def write_collection_file(collection):
    """写入单个采集单元的数据文件(独立文件,不覆盖其他单元)"""
    os.makedirs(COLLECTIONS_DIR, exist_ok=True)
    path = os.path.join(COLLECTIONS_DIR, "%s.js" % collection["id"])
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("// 采集单元数据: %s (由 generate.py 生成)\n" % collection["title"])
        fh.write("window.COLLECTION_DATA[%s] = %s;\n" % (
            json.dumps(collection["id"]), js(collection)))
    return path


def load_collection_data(unit_id):
    """读取某个采集单元已有的数据,用于增量合并。新位置优先,兼容旧数据文件"""
    path = os.path.join(COLLECTIONS_DIR, "%s.js" % unit_id)
    if not os.path.exists(path):
        path = os.path.join(DATA_DIR, "%s.js" % unit_id)  # 迁移前的旧位置
    if not os.path.exists(path):
        return None
    text = open(path, encoding="utf-8").read()
    m = re.search(r"=\s*(\{.*\})\s*;\s*$", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


# 兼容旧函数名
load_topic_data = load_collection_data


def meta_from_collection(collection, created=None):
    """从采集单元提取索引元信息(不含视频列表)"""
    meta = {k: v for k, v in collection.items() if k != "videos"}
    videos = collection.get("videos") or []
    if videos:
        meta["cover"] = videos[0].get("cover", "")
        meta["latest"] = videos[0].get("date", "")
    meta["count"] = len(videos)
    if created:
        meta["created"] = created
    meta["updated"] = datetime.date.today().isoformat()
    return meta


def save_collection(collection, index):
    """写入单元数据文件并更新索引中的对应条目(只动这一个单元)"""
    os.makedirs(COLLECTIONS_DIR, exist_ok=True)
    data_path = write_collection_file(collection)
    unit_id = collection["id"]
    existing = next((t for t in index if t.get("id") == unit_id), None)
    created = existing.get("created") if existing else datetime.date.today().isoformat()
    meta = meta_from_collection(collection, created=created)
    # 保留原有显示开关:重新采集不应改变用户的开关状态
    if existing and "enabled" in existing:
        meta["enabled"] = existing["enabled"]
    index = [t for t in index if t.get("id") != unit_id]
    index.append(meta)
    write_index(index, datetime.date.today().isoformat())
    return data_path, index


def set_enabled(unit_id, enabled, log=print):
    """开启/关闭某个采集单元的显示:同步改索引和数据文件,不动其他单元"""
    index = load_index()
    target = next((t for t in index if t.get("id") == unit_id), None)
    if not target:
        return {"ok": False, "error": "未找到采集单元: %s" % unit_id}
    target["enabled"] = bool(enabled)
    write_index(index, datetime.date.today().isoformat())
    # 数据文件内也保存开关,便于单独还原/迁移
    data = load_collection_data(unit_id)
    if data is not None:
        data["enabled"] = bool(enabled)
        os.makedirs(COLLECTIONS_DIR, exist_ok=True)
        with open(os.path.join(COLLECTIONS_DIR, "%s.js" % unit_id), "w", encoding="utf-8") as fh:
            fh.write("// 采集单元数据: %s (由 generate.py 生成)\n" % data.get("title", ""))
            fh.write("window.COLLECTION_DATA[%s] = %s;\n" % (json.dumps(unit_id), js(data)))
    log("%s 显示已%s: %s" % (unit_id, "开启" if enabled else "关闭", target.get("title", "")))
    return {"ok": True, "id": unit_id, "enabled": bool(enabled), "title": target.get("title", "")}


def merge_videos(existing, incoming):
    """
    增量合并 + 去重(纯规则):
      - 以 BV 号为唯一键,同一视频只保留一条
      - 新采集到的数据覆盖旧数据(刷新播放量/简介)
      - 旧有但本次未搜到的视频保留,避免搜索排序波动导致数据丢失
    返回 (合并后列表, 报告dict)
    """
    old_map = {v.get("bv"): v for v in (existing or []) if v.get("bv")}
    report = {"added": 0, "updated": 0, "kept": 0, "total": 0}

    for v in incoming:
        bv = v.get("bv")
        if not bv:
            continue
        if bv in old_map:
            old = old_map[bv]
            changed = (
                old.get("views") != v.get("views")
                or old.get("title") != v.get("title")
                or old.get("desc") != v.get("desc")
                or (v.get("ts") and not old.get("ts"))  # 回填时间戳也视为更新
            )
            if changed:
                report["updated"] += 1
            else:
                report["kept"] += 1
            # 新数据没有 ts 时,保留旧数据已有的 ts
            if not v.get("ts") and old.get("ts"):
                v["ts"] = old["ts"]
            old_map[bv] = v  # 用最新数据覆盖
        else:
            report["added"] += 1
            old_map[bv] = v

    def sort_key(v):
        if v.get("ts"):
            return (1, v["ts"])
        # 新格式 yyyy.mm.dd;兼容旧格式 X年X月X日
        m = re.match(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", v.get("date", ""))
        if not m:
            m = re.match(r"(?:(\d{4})年)?(\d+)月(\d+)日", v.get("date", ""))
        if m:
            # 无时间戳时按 年/月/日 估算;缺年份则按 0 年,排在有 ts 的之后
            year = int(m.group(1)) if m.group(1) else 0
            return (0, year * 10000 + int(m.group(2)) * 100 + int(m.group(3)))
        return (0, 0)
    merged = sorted(old_map.values(), key=sort_key, reverse=True)
    report["total"] = len(merged)
    return merged, report


def collect_topic(keyword, pages=30, title=None, up=None, slug=None,
                  slogan=None, min_match=2, match_all=False, dry_run=False,
                  unit_id=None, log=print):
    """
    按主题采集一个 series 单元。可被命令行和 Web 服务共同调用。
    只写数据,不生成页面;命中已有 id 时只更新该单元,不动其他单元。
    """
    result = {
        "ok": False, "keyword": keyword, "error": None,
        "added": 0, "updated": 0, "kept": 0, "total": 0,
        "fetched": 0, "author": "", "data_file": "", "page_file": "",
        "sample_url": "", "topic_count": 0, "unit_id": "", "type": "series",
    }
    keyword = (keyword or "").strip()
    if not keyword:
        result["error"] = "主题关键词不能为空"
        return result

    log("主题: %s" % keyword)
    log("正在搜索 B站 (最多 %d 页)..." % pages)
    items = search_bilibili(keyword, pages, verbose=False)
    result["fetched"] = len(items)
    log("共抓取 %d 条结果,正在聚类同系列..." % len(items))

    chosen, ranked = pick_series(items, keyword, up, min_match, match_all)
    if not chosen:
        result["error"] = "未找到匹配视频。关键词需完整出现在标题中(不拆分),请检查关键词是否准确;或取消「指定UP主」再试"
        log(result["error"])
        return result

    author = up or chosen[0].get("author", "")
    mid = chosen[0].get("mid", "")
    result["author"] = author
    log("识别系列: UP主「%s」,命中 %d 期" % (author, len(chosen)))
    if not up and ranked:
        log("候选UP主: %s" % ", ".join("%s(%d)" % (a, c) for a, c in ranked))

    incoming = [normalize(v, keyword) for v in chosen]
    seen, incoming_unique = set(), []
    for v in incoming:
        if v["bv"] and v["bv"] not in seen:
            seen.add(v["bv"])
            incoming_unique.append(v)

    index = load_index()
    existing_ids = {t.get("id") for t in index}
    title = (title or "").strip() or keyword
    matched = next((t for t in index if t.get("title") == title), None)

    # 指定 id 优先级最高:命中已有单元则只更新它
    wanted = (unit_id or slug or "").strip()
    if wanted:
        uid = re.sub(r"[^a-zA-Z0-9_-]", "", wanted) or "topic"
    elif matched:
        uid = matched["id"]
    else:
        uid = slugify(keyword, None, existing_ids)
    result["unit_id"] = uid
    is_update = uid in existing_ids

    existing_data = load_collection_data(uid)
    videos, report = merge_videos(existing_data.get("videos") if existing_data else [], incoming_unique)
    result.update(report)
    result["sample_url"] = videos[0]["url"] if videos else ""

    log("去重合并: 新增 %d / 更新 %d / 未变 %d / 合计 %d 期" % (
        report["added"], report["updated"], report["kept"], report["total"]))

    if dry_run:
        log("\n[dry-run] 未写文件")
        for v in videos[:20]:
            log("%s | %s | %s | %s" % (v["bv"], v["date"], v["views"], v["title"]))
        result["ok"] = True
        return result

    unchanged = (
        existing_data
        and report["added"] == 0
        and report["updated"] == 0
        and report["kept"] == len(videos)
    )
    if unchanged:
        log("数据无更新,跳过写文件")
        result["ok"] = True
        result["data_file"] = "assets/data/collections/%s.js" % uid
        result["page_file"] = "series.html?id=%s" % uid
        result["topic_count"] = len(index)
        return result

    page_path = "series.html?id=%s" % uid
    final_slogan = slogan or "共收录 %d 期,点击卡片跳转 B站观看" % len(videos)
    # 标签:取系列最新一期的视频标签(正式标签,来自实际采集内容),仅请求 1 次避免限流;
    # 获取失败或为空时退回主题关键词,保证首页筛选有内容
    latest_raw = max(chosen, key=lambda v: v.get("pubdate", 0) or 0)
    unit_tags = fetch_video_tags(latest_raw.get("bvid", ""), log=log)
    if not unit_tags:
        unit_tags = [keyword]
    collection = {
        "id": uid,
        "type": "series",
        "title": title,
        "slogan": final_slogan,
        "source": {
            "platform": "B站",
            "name": author,
            "url": "https://space.bilibili.com/%s/video" % mid if mid else "https://www.bilibili.com/",
        },
        "keyword": keyword,
        "tags": unit_tags[:10],
        "page": page_path,
        "count": len(videos),
        "videos": videos,
    }
    data_path, index = save_collection(collection, index)

    result["ok"] = True
    result["data_file"] = os.path.relpath(data_path, ROOT)
    result["page_file"] = page_path
    result["topic_count"] = len(index)
    log("采集完成: %s" % result["data_file"])
    log("数据单元页: %s" % page_path)
    log("采集索引: assets/data/index.js (共 %d 个单元,本次%s)" % (len(index), "更新" if is_update else "新建"))
    log("跳转地址: %s" % result["sample_url"])
    return result


def extract_bvid(text):
    """
    从 B站 链接/分享文案中解析 BV 号:
      1) 文本中直接含 BV 号 → 直接返回
      2) 含 b23.tv 短链 → 跟随重定向拿到最终视频页 URL,再提取 BV
      3) 支持短链后带查询参数、文案中夹带标点等常见格式
    """
    text = (text or "").strip()
    m = re.search(r"(BV[0-9A-Za-z]{10})", text)
    if m:
        return m.group(1)
    # b23.tv 短链:跟随重定向解析
    short = re.search(r"https?://b23\.tv/[A-Za-z0-9]+", text)
    if short:
        try:
            req = urllib.request.Request(short.group(0), headers=make_headers())
            with urllib.request.urlopen(req, timeout=20) as resp:
                final = resp.geturl()
            m = re.search(r"(BV[0-9A-Za-z]{10})", final)
            if m:
                return m.group(1)
        except Exception:
            pass
    return ""


def extract_share_title(text):
    """
    从 B站 分享文案中提取标题,形如:
      【标题正文-哔哩哔哩】 https://b23.tv/xxx
    取 【】内内容,去掉结尾的「-哔哩哔哩」等平台后缀。
    """
    text = (text or "").strip()
    m = re.search(r"【([^】]+)】", text)
    if not m:
        return ""
    title = m.group(1).strip()
    # 去掉常见的平台后缀,如「-哔哩哔哩」「_哔哩哔哩_bilibili」
    title = re.sub(r"[-_]\s*哔哩哔哩.*$", "", title).strip()
    title = re.sub(r"[-_]\s*bilibili.*$", "", title, flags=re.I).strip()
    return title


def fetch_video_by_bvid(bvid, log=print):
    """调用 B站 视频详情 API 获取单条视频,返回搜索API同构的 dict,供 normalize 复用"""
    url = "https://api.bilibili.com/x/web-interface/view?" + urllib.parse.urlencode({"bvid": bvid})
    req = urllib.request.Request(url, headers=make_headers())
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("code") != 0:
        raise ValueError("B站 返回 code=%s: %s" % (data.get("code"), data.get("message")))
    x = data["data"]
    owner = x.get("owner") or {}
    return {
        "bvid": x.get("bvid"),
        "title": x.get("title", ""),
        "pic": x.get("pic", ""),
        "description": x.get("desc", ""),
        "pubdate": x.get("pubdate", 0),
        "author": owner.get("name", ""),
        "mid": owner.get("mid", ""),
        "play": (x.get("stat") or {}).get("view", 0),
        "duration": x.get("duration", 0),
    }


def fetch_video_tags(bvid, log=print):
    """
    获取视频标签名列表(最多前 10 个),用于首页筛选与页面展示。
    依次尝试两个官方端点(接口偶有调整),全部失败时返回空列表,不阻断采集。
    """
    endpoints = [
        "https://api.bilibili.com/x/web-interface/view/detail/tag?",
        "https://api.bilibili.com/x/tag/archive/tags?",
    ]
    for base in endpoints:
        try:
            url = base + urllib.parse.urlencode({"bvid": bvid})
            req = urllib.request.Request(url, headers=make_headers())
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if data.get("code") != 0:
                log("  标签接口返回 code=%s (%s)" % (data.get("code"), base))
                continue
            names = [(t or {}).get("tag_name", "") for t in (data.get("data") or [])]
            names = [n.strip() for n in names if n.strip()]
            if names:
                return names[:10]
        except Exception as exc:
            log("  获取标签失败(不影响采集): %s (%s)" % (exc, base))
    return []


def collect_by_url(url, title=None, slug=None, slogan=None, dry_run=False,
                   unit_id=None, log=print):
    """
    按 B站 视频链接采集单条视频,写入一个 single 单元。
    与 collect_topic 共用 normalize / merge / 写文件逻辑,但来源是详情 API。
    """
    result = {
        "ok": False, "keyword": "", "error": None,
        "added": 0, "updated": 0, "kept": 0, "total": 0,
        "fetched": 0, "author": "", "data_file": "", "page_file": "",
        "sample_url": "", "topic_count": 0, "bvid": "", "unit_id": "", "type": "single",
    }
    bvid = extract_bvid(url)
    if not bvid:
        result["error"] = "未能从链接中解析出 BV 号,请粘贴 B站 视频页链接、b23.tv 短链或 BV 号"
        return result
    result["bvid"] = bvid
    result["keyword"] = bvid
    log("解析到 BV 号: %s" % bvid)
    share_title = extract_share_title(url)
    if share_title:
        log("从分享文案提取标题: %s" % share_title[:60])
    log("正在获取视频详情...")
    try:
        raw = fetch_video_by_bvid(bvid, log=log)
    except Exception as exc:
        result["error"] = "获取视频详情失败: %s" % exc
        log(result["error"])
        return result
    result["fetched"] = 1
    result["author"] = raw.get("author", "")

    video = normalize(raw, "")
    # 标签:单片采集时请求一次标签接口,用于首页筛选与页面展示(失败不阻断)
    tags = fetch_video_tags(bvid, log=log)
    if tags:
        video["tags"] = tags
        log("标签: %s" % " / ".join(tags[:6]))
    incoming = [video] if video.get("bv") else []
    if not incoming:
        result["error"] = "视频数据不完整,无法生成单元"
        return result
    log("标题: %s" % video["title"])
    log("UP主: %s | 发布: %s" % (video["author"], video["date"]))

    index = load_index()
    existing_ids = {t.get("id") for t in index}
    final_title = (title or "").strip() or share_title or video["title"]

    # 指定 id 优先;否则默认用 BV 号(稳定),已存在则复用
    wanted = (unit_id or slug or "").strip()
    if wanted:
        uid = re.sub(r"[^a-zA-Z0-9_-]", "", wanted) or bvid.lower()
    else:
        uid = next((t["id"] for t in index if t.get("title") == final_title),
                   bvid.lower())
    result["unit_id"] = uid
    is_update = uid in existing_ids

    existing_data = load_collection_data(uid)
    videos, report = merge_videos(existing_data.get("videos") if existing_data else [], incoming)
    result.update(report)
    result["sample_url"] = videos[0]["url"] if videos else ""
    log("去重合并: 新增 %d / 更新 %d / 未变 %d / 合计 %d 期" % (
        report["added"], report["updated"], report["kept"], report["total"]))

    if dry_run:
        log("\n[dry-run] 未写文件")
        log("%s | %s | %s | %s" % (video["bv"], video["date"], video["views"], video["title"]))
        result["ok"] = True
        return result

    unchanged = (
        existing_data
        and report["added"] == 0
        and report["updated"] == 0
        and report["kept"] == len(videos)
    )
    if unchanged:
        log("数据无更新,跳过写文件")
        result["ok"] = True
        result["data_file"] = "assets/data/collections/%s.js" % uid
        result["page_file"] = "single.html?id=%s" % uid
        result["topic_count"] = len(index)
        return result

    page_path = "single.html?id=%s" % uid
    final_slogan = slogan or "单条视频精选 · 点击卡片跳转 B站观看"
    # 单元标签:视频标签优先;没有标签时退回标题关键词,保证首页筛选有内容
    unit_tags = list(tags)
    if not unit_tags:
        kw = re.sub(r"\s+", "", final_title or "")
        unit_tags = [kw] if kw else []
    collection = {
        "id": uid,
        "type": "single",
        "title": final_title,
        "slogan": final_slogan,
        "source": {
            "platform": "B站",
            "name": video["author"],
            "url": ("https://space.bilibili.com/%s/video" % raw.get("mid")) if raw.get("mid") else video["url"],
        },
        "keyword": url,
        "tags": unit_tags[:10],
        "page": page_path,
        "count": len(videos),
        "videos": videos,
    }
    data_path, index = save_collection(collection, index)

    result["ok"] = True
    result["data_file"] = os.path.relpath(data_path, ROOT)
    result["page_file"] = page_path
    result["topic_count"] = len(index)
    log("采集完成: %s" % result["data_file"])
    log("数据单元页: %s" % page_path)
    log("采集索引: assets/data/index.js (共 %d 个单元,本次%s)" % (len(index), "更新" if is_update else "新建"))
    log("跳转地址: %s" % result["sample_url"])
    return result


def migrate_legacy(log=print):
    """
    把旧格式(assets/data/<id>.js 的 TOPIC_DATA + index.js 的 TOPIC_INDEX)
    迁移到新格式(collections/<id>.js + COLLECTION_INDEX)。
    旧文件不删除,只新增新格式文件并重建索引,可安全重复执行。
    """
    index = load_index()
    migrated = 0
    for meta in index:
        uid = meta.get("id")
        if not uid:
            continue
        new_path = os.path.join(COLLECTIONS_DIR, "%s.js" % uid)
        if os.path.exists(new_path):
            # 新格式已存在:只补齐元信息字段
            data = load_collection_data(uid) or {}
            changed = False
            # 纠正类型:BV 号 id 归为 single
            expected_type = "single" if str(uid).lower().startswith("bv") else "series"
            if data.get("type") != expected_type:
                data["type"] = expected_type
                changed = True
            expected_page = ("single.html?id=%s" if expected_type == "single"
                             else "series.html?id=%s") % uid
            if data.get("page") != expected_page:
                data["page"] = expected_page
                changed = True
            for key in ("enabled", "created", "updated", "keyword", "count", "cover", "latest"):
                if key not in data and key in meta:
                    data[key] = meta[key]
                    changed = True
            # 采集时间为空(存量迁移)则回填当天,保证子页面「最近采集」有值
            if not data.get("updated"):
                data["updated"] = datetime.date.today().isoformat()
                changed = True
            # 标签缺失则用标题关键词兜底,保证首页筛选可用
            if not data.get("tags"):
                data["tags"] = [data["title"]] if data.get("title") else []
                changed = changed or bool(data["tags"])
            data.setdefault("enabled", True)
            if changed:
                with open(new_path, "w", encoding="utf-8") as fh:
                    fh.write("// 采集单元数据: %s (迁移自旧格式)\n" % data.get("title", ""))
                    fh.write("window.COLLECTION_DATA[%s] = %s;\n" % (json.dumps(uid), js(data)))
            continue
        data = load_collection_data(uid)
        if not data:
            log("跳过 %s: 未找到数据" % uid)
            continue
        # BV 号 id 历史上来自「按链接采集」,归为 single;其余为 series
        data["type"] = ("single" if uid.lower().startswith("bv")
                        else (meta.get("type") or "series"))
        data["enabled"] = meta.get("enabled", True)
        data["created"] = meta.get("created", "")
        data["updated"] = meta.get("updated") or datetime.date.today().isoformat()
        data["keyword"] = meta.get("keyword", "")
        # 标签缺失则用标题关键词兜底,保证首页筛选可用
        if not data.get("tags"):
            data["tags"] = [data["title"]] if data.get("title") else []
        videos = data.get("videos") or []
        # 旧 single 单元的 page 指向 topics/<id>.html,改为 single.html?id=
        data["page"] = ("single.html?id=%s" if data["type"] == "single" else "series.html?id=%s") % uid
        data["count"] = len(videos)
        if videos and not data.get("cover"):
            data["cover"] = videos[0].get("cover", "")
            data["latest"] = videos[0].get("date", "")
        write_collection_file(data)
        migrated += 1
        log("迁移 %s -> collections/%s.js (type=%s)" % (uid, uid, data["type"]))

    # 重建索引,补齐新字段
    new_index = []
    for meta in load_index():
        uid = meta.get("id")
        t = ("single" if str(uid).lower().startswith("bv")
             else (meta.get("type") or "series"))
        meta["type"] = t
        meta.setdefault("enabled", True)
        meta.setdefault("created", "")
        meta.setdefault("keyword", "")
        # 采集时间为空(存量迁移)则回填当天,与数据文件保持一致
        if not meta.get("updated"):
            meta["updated"] = datetime.date.today().isoformat()
        # 标签缺失则用标题关键词兜底,与数据文件保持一致
        if not meta.get("tags"):
            meta["tags"] = [meta["title"]] if meta.get("title") else []
        meta["page"] = ("single.html?id=%s" if t == "single" else "series.html?id=%s") % uid
        new_index.append(meta)
    write_index(new_index, datetime.date.today().isoformat())
    log("迁移完成: 新增 %d 个单元数据文件,索引共 %d 个单元" % (migrated, len(new_index)))
    return {"ok": True, "migrated": migrated, "total": len(new_index)}


def build_parser():
    parser = argparse.ArgumentParser(description="B站采集数据生成器(纯规则,不使用AI;不生成页面)")
    parser.add_argument("keyword", nargs="?", default=None, help="搜索主题关键词(或 --url 时的链接/BV号)")
    parser.add_argument("--pages", type=int, default=30, help="搜索翻页数,默认30(每页20条)")
    parser.add_argument("--title", default=None, help="显示标题")
    parser.add_argument("--up", default=None, help="限定UP主名称")
    parser.add_argument("--id", dest="unit_id", default=None, help="采集单元 id;命中已有单元则只更新它")
    parser.add_argument("--slug", default=None, help="同 --id,兼容旧参数")
    parser.add_argument("--slogan", default=None, help="副标题")
    parser.add_argument("--min-match", type=int, default=2, help="标题相似度最小词块数,默认2")
    parser.add_argument("--match-all", action="store_true", help="要求包含关键词全部核心词")
    parser.add_argument("--url", action="store_true", help="按链接采集单条视频(type=single)")
    parser.add_argument("--dry-run", action="store_true", help="只预览不写文件")
    parser.add_argument("--list", action="store_true", help="列出所有采集单元")
    parser.add_argument("--toggle", metavar="ID", default=None, help="开启/关闭某单元显示,配合 --on/--off")
    parser.add_argument("--on", dest="toggle_on", action="store_true", help="配合 --toggle:开启显示")
    parser.add_argument("--off", dest="toggle_off", action="store_true", help="配合 --toggle:关闭显示")
    parser.add_argument("--migrate", action="store_true", help="从旧格式迁移到采集单元格式")
    return parser


def main():
    args = build_parser().parse_args()

    if args.migrate:
        r = migrate_legacy()
        if not r["ok"]:
            sys.exit(1)
        return
    if args.list:
        for t in load_index():
            mark = "on " if t.get("enabled", True) else "off"
            print("[%s] %-10s %-14s %s (%s 期)" % (
                mark, t.get("type", "series"), t.get("id"), t.get("title"), t.get("count", 0)))
        return
    if args.toggle:
        if args.toggle_off and not args.toggle_on:
            enabled = False
        else:
            enabled = True
        r = set_enabled(args.toggle, enabled)
        print(r.get("error") or ("%s 显示已%s" % (r["id"], "开启" if r["enabled"] else "关闭")))
        if not r["ok"]:
            sys.exit(1)
        return

    if not args.keyword:
        print("错误:请提供主题关键词/链接,或使用 --list/--toggle/--migrate", file=sys.stderr)
        sys.exit(1)

    if args.url:
        result = collect_by_url(
            url=args.keyword, title=args.title, slug=args.slug,
            slogan=args.slogan, dry_run=args.dry_run, unit_id=args.unit_id,
        )
    else:
        result = collect_topic(
            keyword=args.keyword, pages=args.pages, title=args.title, up=args.up,
            slug=args.slug, slogan=args.slogan, min_match=args.min_match,
            match_all=args.match_all, dry_run=args.dry_run, unit_id=args.unit_id,
        )
    if not result["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
