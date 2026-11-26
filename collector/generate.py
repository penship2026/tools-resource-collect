#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集页 · 采集数据生成器

纯规则程序,不调用任何 AI:
  输入主题关键词 → 调用 B站 公开搜索 API → 按规则聚类同系列视频 → 写入一个采集单元的数据

采集只处理数据,不生成、不修改任何静态页面。页面是三个固定模板(index.html /
series.html / single.html),由人工单独维护布局样式,通过 ?id= 读取对应采集单元的数据。

数据架构:每次采集是一个独立单元,单独存一个数据文件,互不覆盖;重新采集命中
同一 id 时只更新该单元,可单独关闭某单元的显示。
  assets/data/index.js                  索引(各单元元信息 + 显示开关)
  assets/data/collections/<id>.js       该单元的视频数据

支持渠道:B站(视频)、公众号(图文)、小红书(图文/视频)。后两者只做「按链接/批量链接」采集,
主题关键词搜索仍仅 B站(公众号与小红书没有公开可用的搜索接口)。

用法:
  python3 generate.py "每天挖掘一个神奇网站"            # 按主题采集 B站(type=series)
  python3 generate.py "跟着动画学古文" --up "某个UP主"
  python3 generate.py "https://www.bilibili.com/video/BVxxx/" --url   # 按链接采集(type=single)
  python3 generate.py "https://mp.weixin.qq.com/s/xxxx" --url         # 公众号文章(图文)
  python3 generate.py "https://xhslink.com/xxxx" --url                # 小红书笔记
  python3 generate.py --batch "链接1 链接2" --title "AI 与人的边界"     # 批量链接(可混合渠道,type=series)
  python3 generate.py --id daily-website "新关键词"       # 重新采集指定单元,只更新它
  python3 generate.py --toggle daily-website --off        # 关闭某单元显示
  python3 generate.py --toggle daily-website --on         # 开启某单元显示
  python3 generate.py --list                              # 列出所有采集单元

可选参数:
  --url            按链接采集单条内容(type=single,自动识别 B站/公众号/小红书)
  --batch          批量采集:位置参数传入多行链接/分享文案,可混合多个渠道
  --manual-title T 抓取失败时手工补录标题(公众号/小红书风控时可用)
  --manual-author A / --manual-desc D / --manual-date YYYY-MM-DD / --manual-cover URL
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

# 多渠道适配层(公众号/小红书),与 B站 采集并列
import platforms as channels

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
# 覆盖索引前的自动快照目录(仅本地保留,已在 .gitignore 中排除)
BACKUP_DIR = os.path.join(ROOT, "backups", "auto")
SNAPSHOT_KEEP = 10


class IndexCorrupt(Exception):
    """索引文件存在但内容无法解析(用于区分「不存在」与「损坏」)"""


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


def title_match(title, keyword):
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


def pick_series(items, keyword, up_name):
    """
    纯统计规则聚类同系列:
      1. 按标题匹配筛候选
      2. 指定 --up 时按作者过滤(仍要求标题相关)
      3. 否则取候选中频次最高的 UP 主作为系列主账号
    """
    candidates = [
        x for x in items
        if title_match(clean_html(x.get("title", "")), keyword)
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
        "platform": "bilibili",
        "kind": "video",
        # 去重键:跨平台统一用 key,B站用 BV 号
        "key": "bilibili:%s" % bv if bv else "",
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


def item_key(item):
    """
    条目的去重键,跨平台统一:
      - 新采集的条目自带 key(如 bilibili:BVxxx / wechat:<文章地址> / xhs:<笔记ID>)
      - 存量 B站 条目可能只有 BV 号,统一补成 bilibili:BVxxx,避免与新格式重复
      - 再退回原文地址,保证任何渠道都能去重
    """
    item = item or {}
    key = (item.get("key") or "").strip()
    bv = (item.get("bv") or "").strip()
    if key and ":" not in key:
        key = ("bilibili:" + key) if (bv or key.upper().startswith("BV")) else key
    if not key and bv:
        key = "bilibili:" + bv
    return key or (item.get("url") or "").strip()


def display_path(path):
    """日志里展示的路径:在项目内用相对路径,数据目录被指到项目外时用绝对路径"""
    try:
        rel = os.path.relpath(path, ROOT)
    except Exception:
        return path
    return path if rel.startswith("..") else rel


def platform_label(key):
    """平台标识 → 展示名称;B站为空时按老数据处理"""
    if not key:
        return "B站"
    return channels.platform_name(key) or key


# 渠道稳定 key(D24):数据里只存 key,中文展示名由前端映射
PLATFORM_KEYS = ("bilibili", "wechat", "xhs", "multi")
_PLATFORM_LABEL_TO_KEY = {"B站": "bilibili", "公众号": "wechat", "小红书": "xhs", "多平台": "multi"}


def platform_key(value):
    """展示名/旧值 → 稳定 key;未知值原样返回(由 --verify 报出)"""
    v = str(value or "").strip()
    if not v:
        return "bilibili"
    if v in PLATFORM_KEYS:
        return v
    return _PLATFORM_LABEL_TO_KEY.get(v, v)


def normalize_date(text):
    """把各种日期写法统一成 yyyy.mm.dd,无法识别时原样返回"""
    m = re.match(r"(\d{4})[-./年](\d{1,2})[-./月](\d{1,2})", (text or "").strip())
    if not m:
        return (text or "").strip() or "—"
    return "%s.%s.%s" % (m.group(1), m.group(2).zfill(2), m.group(3).zfill(2))


def guess_tags(title, extra=()):
    """
    文章类内容没有平台标签,用标题片段做标签兜底,保证首页筛选有内容。
    只保留 2-12 字的片段,最多 6 个。
    """
    tags = []
    for raw in list(extra) + re.split(r"[|｜/、,，:：\-—_()（）\[\]【】]+", title or ""):
        token = (raw or "").strip()
        if 2 <= len(token) <= 12 and token not in tags:
            tags.append(token)
    return tags[:6]


def article_item(raw, platform_key):
    """把适配层返回的文章结构转成站点条目(与 B站 normalize 后的结构对齐)"""
    tags = [t for t in (raw.get("tags") or []) if t]
    if not tags:
        tags = guess_tags(raw.get("title", ""), [raw.get("source_name") or ""])
    return {
        "platform": raw.get("platform") or platform_key,
        "kind": raw.get("kind") or channels.platform_kind(platform_key),
        "key": raw.get("key") or ("%s:%s" % (platform_key, raw.get("url", ""))),
        "title": raw.get("title", ""),
        "bv": "",
        # 图文内容没有 BV 号,用平台编号占位展示(公众号短链末段 / 小红书笔记ID)
        "vid": (raw.get("key") or "").split(":", 1)[-1][-24:],
        "url": raw.get("url", ""),
        "cover": raw.get("cover", ""),
        "views": "",
        "date": normalize_date(raw.get("date", "")),
        "ts": raw.get("ts") or 0,
        "author": raw.get("author") or raw.get("source_name") or "",
        "desc": (raw.get("desc") or "")[:160],
        "tags": tags[:10],
    }


def manual_item(url, platform_key, manual):
    """抓取被风控时的手工补录:只有标题必填,其余留空也能建单元"""
    manual = manual or {}
    title = (manual.get("title") or "").strip()
    author = (manual.get("author") or "").strip()
    return {
        "platform": platform_key,
        "kind": channels.platform_kind(platform_key),
        "key": "%s:%s" % (platform_key, url),
        "title": title,
        "bv": "",
        "vid": "",
        "url": url,
        "cover": (manual.get("cover") or "").strip(),
        "views": "",
        "date": normalize_date(manual.get("date") or ""),
        "ts": 0,
        "author": author,
        "desc": (manual.get("desc") or "").strip()[:160],
        "tags": guess_tags(title, [author]),
    }


def load_index(strict=False):
    """读取采集单元索引,返回元信息列表(每个单元一条)

    strict=True 时,文件存在但无法解析会抛 IndexCorrupt,供健康检查区分
    「索引不存在」与「索引损坏」;默认宽松模式仍返回 [],保持既有调用方兼容。
    """
    if not os.path.exists(INDEX_JS):
        return []
    try:
        text = open(INDEX_JS, encoding="utf-8").read()
        # 优先读新格式 window.COLLECTION_INDEX,兼容 const 声明与旧格式 TOPIC_INDEX
        m = re.search(r"(?:window\.)?(?:const\s+)?(?:COLLECTION_INDEX|TOPIC_INDEX)\s*=\s*(\[.*\])\s*;", text, re.S)
        if not m:
            raise IndexCorrupt("未找到 COLLECTION_INDEX 声明")
        items = json.loads(m.group(1))
        if not isinstance(items, list):
            raise IndexCorrupt("索引内容不是数组")
    except IndexCorrupt as exc:
        print("  错误:采集索引损坏(%s): %s" % (INDEX_JS, exc), file=sys.stderr)
        if strict:
            raise
        return []
    except Exception as exc:
        print("  错误:读取采集索引失败(%s): %s" % (INDEX_JS, exc), file=sys.stderr)
        if strict:
            raise IndexCorrupt(str(exc))
        return []
    # 旧格式补齐默认字段,让页面与接口都能直接用
    for it in items:
        it.setdefault("type", "series")
        it.setdefault("enabled", True)
        it.setdefault("created", "")
        it.setdefault("updated", "")
    return items


def index_status():
    """索引健康状态:供 /api/health 与 --verify 使用,避免把「损坏」当成「空站」"""
    if not os.path.exists(INDEX_JS):
        return {"ok": False, "count": 0, "reason": "索引文件不存在"}
    try:
        return {"ok": True, "count": len(load_index(strict=True)), "reason": ""}
    except IndexCorrupt as exc:
        return {"ok": False, "count": 0, "reason": str(exc)}


DATE_RE = re.compile(r"^\d{4}[.\-]\d{2}[.\-]\d{2}$")
# 主题注册表(D32/D40):与 assets/theme.js 的 THEMES 保持一致。单元级 theme 只做提示,不启用渲染分支。
THEME_NAMES = ("default", "dark", "tech", "campus", "classical", "anime")


def _bad_platform(value):
    """platform 取值是否非稳定 key(列表逐项检查)"""
    if isinstance(value, list):
        return any(_bad_platform(v) for v in value)
    if value is None or value == "":
        return False
    return str(value) not in PLATFORM_KEYS


def verify_data(log=print):
    """数据一致性自检(D13):索引与数据文件一一对应、count 与 videos 一致、
    key 唯一、日期格式、开关两处一致。返回 {"ok", "problems", "units"}。"""
    problems = []
    st = index_status()
    if not st["ok"]:
        log("  ✗ 索引不可用: %s" % st["reason"])
        return {"ok": False, "problems": ["索引不可用: %s" % st["reason"]], "units": 0}
    items = load_index()
    ids = [t.get("id") for t in items if t.get("id")]
    units = 0
    for t in items:
        uid = t.get("id") or ""
        if not uid:
            problems.append("索引中存在缺少 id 的条目")
            continue
        path = os.path.join(COLLECTIONS_DIR, "%s.js" % uid)
        data = load_collection_data(uid)
        if data is None:
            problems.append("%s: 数据文件缺失或无法解析(%s)" % (uid, display_path(path)))
            continue
        units += 1
        vids = data.get("videos") or []
        if data.get("id") != uid:
            problems.append("%s: 数据文件里的 id 不一致(%s)" % (uid, data.get("id")))
        if int(t.get("count", -1)) != len(vids):
            problems.append("%s: 索引 count=%s,数据 videos=%d" % (uid, t.get("count"), len(vids)))
        keys = {}
        for i, v in enumerate(vids):
            k = item_key(v)
            if not k:
                problems.append("%s: 第 %d 条缺少 key" % (uid, i + 1))
            elif k in keys:
                problems.append("%s: key 重复(%s)" % (uid, k))
            else:
                keys[k] = 1
            d = str(v.get("date") or "")
            if d and not DATE_RE.match(d):
                problems.append("%s: 第 %d 条日期格式异常(%s)" % (uid, i + 1, d))
            if not str(v.get("title") or "").strip():
                problems.append("%s: 第 %d 条缺少标题" % (uid, i + 1))
        # D24:数据里不得再出现表现层 page 字段;platform 只允许稳定 key
        for label, obj in (("索引", t), ("数据", data)):
            if "page" in obj:
                problems.append("%s: %s 仍含表现层 page 字段(应运行 --normalize)" % (uid, label))
        dirty_plats = [p for p in ((data.get("source") or {}).get("platform"),
                                   (t.get("source") or {}).get("platform"),
                                   data.get("platforms"), t.get("platforms"))
                       if _bad_platform(p)]
        if dirty_plats:
            problems.append("%s: platform 存在非稳定 key 取值(%s)" % (uid, dirty_plats))
        if data.get("theme") and data.get("theme") not in THEME_NAMES:
            problems.append("%s: theme 取值不在主题注册表内(%s)" % (uid, data.get("theme")))
        if "enabled" in data and bool(data.get("enabled")) != bool(t.get("enabled", True)):
            problems.append("%s: 显示开关两处不一致(索引 %s / 数据 %s)" % (
                uid, t.get("enabled", True), data.get("enabled")))
    # 反向检查:数据目录里存在但索引没登记(遗留文件/手工拷贝)
    if os.path.isdir(COLLECTIONS_DIR):
        for fn in sorted(os.listdir(COLLECTIONS_DIR)):
            if fn.endswith(".js") and fn[:-3] not in ids:
                problems.append("%s: 数据文件未登记到索引" % fn)
    for p in problems:
        log("  ✗ %s" % p)
    log("  检查单元 %d 个,问题 %d 项" % (units, len(problems)))
    return {"ok": not problems, "problems": problems, "units": units}


def snapshot_file(path, keep=SNAPSHOT_KEEP):
    """覆盖前把现有文件复制一份到 backups/auto,只保留最近 keep 份"""
    if not os.path.exists(path):
        return None
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        base = os.path.splitext(os.path.basename(path))[0]
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
        dest = os.path.join(BACKUP_DIR, "%s-%s.js" % (base, stamp))
        with open(path, "rb") as src, open(dest, "wb") as dst:
            dst.write(src.read())
        olds = sorted(f for f in os.listdir(BACKUP_DIR) if f.startswith(base + "-"))
        for name in olds[:-keep]:
            try:
                os.remove(os.path.join(BACKUP_DIR, name))
            except OSError:
                pass
        return dest
    except OSError as exc:
        # 快照失败不影响主写入,但要在日志里留痕
        print("  警告:写入前快照失败(%s): %s" % (path, exc), file=sys.stderr)
        return None


def write_text_atomic(path, text, snapshot=False):
    """原子写入:先写同目录临时文件再 os.replace,中断不会留下半截文件"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        if snapshot:
            snapshot_file(path)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    return path


def write_index(items, updated):
    """重写采集单元索引文件"""
    lines = [
        "// 采集单元索引,由 generate.py 自动生成",
        "// 挂到 window 上,页面中用 window.COLLECTION_INDEX 读取(const 不会挂到 window)",
        "window.SITE = {",
        "  name: %s," % json.dumps("集页", ensure_ascii=False),
        "  description: %s," % json.dumps("一集一页,把值得收藏的内容收成清单", ensure_ascii=False),
        "  updated: %s," % json.dumps(updated),
        "};",
        "window.COLLECTION_INDEX = %s;" % json.dumps(items, ensure_ascii=False, indent=2),
    ]
    # 索引是首页的唯一入口,覆盖前留快照,写入走原子替换
    write_text_atomic(INDEX_JS, "\n".join(lines) + "\n", snapshot=True)


def write_collection_file(collection):
    """写入单个采集单元的数据文件(独立文件,不覆盖其他单元)"""
    os.makedirs(COLLECTIONS_DIR, exist_ok=True)
    path = os.path.join(COLLECTIONS_DIR, "%s.js" % collection["id"])
    text = ("// 采集单元数据: %s (由 generate.py 生成)\n" % collection["title"]) + \
           ("window.COLLECTION_DATA[%s] = %s;\n" % (
               json.dumps(collection["id"]), js(collection)))
    write_text_atomic(path, text, snapshot=True)
    return path


def load_collection_data(unit_id):
    """读取某个采集单元已有的数据,用于增量合并(只读 collections/ 下新位置)"""
    path = os.path.join(COLLECTIONS_DIR, "%s.js" % unit_id)
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
    """从采集单元提取索引元信息(不含视频列表,采集记录也只留摘要,避免索引膨胀)"""
    meta = {k: v for k, v in collection.items()
            if k not in ("videos", "runs", "intake")}
    videos = collection.get("videos") or []
    if videos:
        meta["cover"] = videos[0].get("cover", "")
        meta["latest"] = videos[0].get("date", "")
    meta["count"] = len(videos)
    # 最近一次采集的填写方式与时间:列表里直接显示,不需要再读数据文件
    intake = collection.get("intake") or {}
    if intake:
        meta["last_at"] = intake.get("at", "")
        meta["last_mode"] = intake.get("mode", "")
        meta["last_mode_label"] = MODE_LABELS.get(intake.get("mode", ""), "")
    if created:
        meta["created"] = created
    meta["updated"] = datetime.date.today().isoformat()
    return meta


def save_collection(collection, index):
    """写入单元数据文件并更新索引中的对应条目(只动这一个单元)"""
    os.makedirs(COLLECTIONS_DIR, exist_ok=True)
    # 单元数据文件里也记下采集时间与最新日期:页面直接读数据文件,缺了会显示「—」
    collection["updated"] = datetime.date.today().isoformat()
    videos = collection.get("videos") or []
    if videos:
        collection["latest"] = videos[0].get("date", "")
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


def _finalize_unit(uid, unit_type, title, slogan, source, videos, tags, keyword,
                   existing_data, intake, report, index, platforms=None):
    """D15:采集单元收口的唯一实现。

    组装字段(id/type/title/slogan/source/keyword/tags/count/videos,可选 platforms)
    → 记录本次填写信息与统计 → 原子写数据文件并重建索引。
    返回 (data_path, index);调用方只负责算字段,不再各拼一份 dict。
    """
    collection = {
        "id": uid,
        "type": unit_type,
        "title": title,
        "slogan": slogan,
        "source": source,
        "keyword": keyword,
        "tags": (tags or [])[:10],
        "count": len(videos),
        "videos": videos,
    }
    if platforms:
        collection["platforms"] = list(platforms)
    collection = attach_intake(collection, existing_data, intake, report)
    return save_collection(collection, index)


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
        text = ("// 采集单元数据: %s (由 generate.py 生成)\n" % data.get("title", "")) + \
               ("window.COLLECTION_DATA[%s] = %s;\n" % (json.dumps(unit_id), js(data)))
        write_text_atomic(os.path.join(COLLECTIONS_DIR, "%s.js" % unit_id), text, snapshot=True)
    log("%s 显示已%s: %s" % (unit_id, "开启" if enabled else "关闭", target.get("title", "")))
    return {"ok": True, "id": unit_id, "enabled": bool(enabled), "title": target.get("title", "")}


# 采集方式的中文名:采集记录、回填提示里统一使用
MODE_LABELS = {"url": "按链接采集", "batch": "批量链接采集", "keyword": "按主题采集"}


def now_stamp():
    """当前时间,精确到分钟:2026-11-26 08:55"""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def normalize_intake(raw):
    """
    规整本次采集的「填写信息」,字段与采集表单一一对应:
    采集方式 / 输入内容 / 显示标题 / UP主 / 页数 / 手工补录。
    存进单元后,下次重新采集可原样回填,不需要用户重新粘贴。
    """
    if not raw:
        return None
    mode = (raw.get("mode") or "url").strip()
    if mode not in MODE_LABELS:
        mode = "url"
    manual = {}
    for key in ("title", "author", "desc", "date", "cover"):
        value = (raw.get("manual_" + key) or "").strip()
        if value:
            manual[key] = value
    try:
        pages = int(raw.get("pages"))
    except (TypeError, ValueError):
        pages = 30
    if pages <= 0:
        pages = 30
    return {
        "mode": mode,
        "input": (raw.get("input") or "").strip()[:8000],
        "title": (raw.get("title") or "").strip(),
        "up": (raw.get("up") or "").strip(),
        "pages": pages,
        # 按主题采集勾选的渠道,重新采集时原样带回表单
        "channels": normalize_topic_channels(raw.get("channels")) if mode == "keyword" else [],
        "manual": manual,
        "at": (raw.get("at") or "").strip() or now_stamp(),
    }


def _intake_input_count(intake):
    """本次输入含几条链接/关键词,记录里显示「3 条链接」"""
    text = intake.get("input") or ""
    if intake.get("mode") == "batch":
        return len(channels.extract_urls(text))
    return 1 if text else 0


def _make_run(intake, title, report):
    """一条采集记录:什么时候、用什么方式、采了几条、标题是什么"""
    return {
        "at": intake.get("at") or now_stamp(),
        "mode": intake.get("mode", ""),
        "mode_label": MODE_LABELS.get(intake.get("mode", ""), intake.get("mode", "")),
        "input_count": _intake_input_count(intake),
        "title": title or "",
        "added": report.get("added", 0),
        "updated": report.get("updated", 0),
        "kept": report.get("kept", 0),
        "total": report.get("total", 0),
    }


def attach_intake(collection, existing, intake, report):
    """把本次采集的填写信息与统计写入单元(保留最近 20 次记录)"""
    if not intake:
        return collection
    runs = list((existing or {}).get("runs") or [])
    runs.insert(0, _make_run(intake, collection.get("title", ""), report))
    collection["intake"] = intake
    collection["runs"] = runs[:20]
    return collection


def record_intake_only(unit_id, intake, report, title=None, log=print):
    """
    采集结果没有变化时,仍然记下本次填写信息;顺带允许只改显示标题。
    返回是否真的写了文件。
    """
    data = load_collection_data(unit_id)
    if data is None or not intake:
        return False
    changed = data.get("intake") != intake
    if title and title != data.get("title"):
        data["title"] = title
        changed = True
    if not changed:
        return False
    data["intake"] = intake
    runs = list(data.get("runs") or [])
    runs.insert(0, _make_run(intake, data.get("title", ""), report))
    data["runs"] = runs[:20]
    write_collection_file(data)
    # 索引同步标题与最近采集时间,列表不用读数据文件就能显示
    today = datetime.date.today().isoformat()
    index = load_index()
    for t in index:
        if t.get("id") == unit_id:
            t["title"] = data.get("title", t.get("title", ""))
            t["last_at"] = intake.get("at", "")
            t["last_mode"] = intake.get("mode", "")
            t["last_mode_label"] = MODE_LABELS.get(intake.get("mode", ""), "")
            t["updated"] = today
    write_index(index, today)
    log("已记录本次采集信息(内容无变化)")
    return True


def update_title(unit_id, title, log=print):
    """
    只更新显示标题,不重新采集内容。
    索引与单元数据文件同时改写,并同步到采集记录里的标题字段。
    """
    unit_id = (unit_id or "").strip()
    title = (title or "").strip()
    if not unit_id:
        return {"ok": False, "error": "缺少单元 id"}
    if not title:
        return {"ok": False, "error": "标题不能为空"}
    index = load_index()
    target = next((t for t in index if t.get("id") == unit_id), None)
    if not target:
        return {"ok": False, "error": "未找到采集单元: %s" % unit_id}
    old_title = target.get("title", "")
    today = datetime.date.today().isoformat()
    target["title"] = title
    target["updated"] = today
    write_index(index, today)
    data = load_collection_data(unit_id)
    if data is not None:
        data["title"] = title
        if data.get("intake"):
            data["intake"] = dict(data["intake"], title=title)
        if data.get("runs"):
            # 历史记录保留当时的标题,只有最新一条跟随本次改名
            runs = list(data["runs"])
            runs[0] = dict(runs[0], title=title)
            data["runs"] = runs
        write_collection_file(data)
    log("标题已更新: %s → %s" % (old_title or "(空)", title))
    page = ("single.html?id=%s" if (target.get("type") or "series") == "single"
            else "series.html?id=%s") % unit_id
    return {"ok": True, "id": unit_id, "title": title, "old_title": old_title,
            "page": page}


def merge_videos(existing, incoming):
    """
    增量合并 + 去重(纯规则):
      - 以条目 key 为唯一键(B站=BV号,公众号=原文地址,小红书=笔记ID),同一内容只保留一条
      - 新采集到的数据覆盖旧数据(刷新标题/简介/封面)
      - 旧有但本次未采集到的条目保留,避免搜索排序波动导致数据丢失
    返回 (合并后列表, 报告dict)
    """
    old_map = {item_key(v): v for v in (existing or []) if item_key(v)}
    report = {"added": 0, "updated": 0, "kept": 0, "total": 0}

    for v in incoming:
        key = item_key(v)
        if not key:
            continue
        if key in old_map:
            old = old_map[key]
            changed = (
                old.get("views") != v.get("views")
                or old.get("title") != v.get("title")
                or old.get("desc") != v.get("desc")
                or old.get("cover") != v.get("cover")
                or (v.get("ts") and not old.get("ts"))  # 回填时间戳也视为更新
            )
            if changed:
                report["updated"] += 1
            else:
                report["kept"] += 1
            # 新数据没有 ts 时,保留旧数据已有的 ts
            if not v.get("ts") and old.get("ts"):
                v["ts"] = old["ts"]
            old_map[key] = v  # 用最新数据覆盖
        else:
            report["added"] += 1
            old_map[key] = v

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


def normalize_topic_channels(value, log=print):
    """
    规整「按主题采集」的渠道多选值:支持数组、逗号分隔字符串和中文名,
    未知渠道忽略,空值退回 B站(与页面默认勾选保持一致)。
    """
    if isinstance(value, str):
        parts = re.split(r"[,，\s|]+", value)
    elif isinstance(value, (list, tuple)):
        parts = []
        for one in value:
            parts.extend(re.split(r"[,，\s|]+", str(one or "")))
    else:
        parts = []
    names = {"bilibili": "bilibili", "b站": "bilibili", "bili": "bilibili",
             "wechat": "wechat", "公众号": "wechat", "wx": "wechat",
             "xhs": "xhs", "小红书": "xhs", "xiaohongshu": "xhs"}
    out = []
    for raw in parts:
        key = names.get((raw or "").strip().lower())
        if key and key not in out:
            out.append(key)
    if not out:
        out = ["bilibili"]
    return out


def collect_topic(keyword, pages=30, title=None, up=None, slug=None,
                  slogan=None, dry_run=False,
                  unit_id=None, log=print, intake=None, topic_channels=None):
    """
    按主题采集一个 series 单元,可同时选 B站 / 公众号 / 小红书多个渠道。
    B站走官方搜索并聚类同系列;公众号 / 小红书借搜索引擎找候选链接,
    公众号再抓正文,小红书以搜索标题 + 原文链接收录(正文需登录)。
    只写数据,不生成页面;命中已有 id 时只更新该单元,不动其他单元。
    """
    result = {
        "ok": False, "keyword": keyword, "error": None,
        "added": 0, "updated": 0, "kept": 0, "total": 0,
        "fetched": 0, "author": "", "data_file": "", "page_file": "",
        "sample_url": "", "topic_count": 0, "unit_id": "", "type": "series",
        "channels": [], "channel_report": [],
    }
    keyword = (keyword or "").strip()
    if not keyword:
        result["error"] = "主题关键词不能为空"
        return result

    selected = normalize_topic_channels(topic_channels, log=log)
    result["channels"] = selected
    log("主题: %s | 渠道: %s" % (keyword, "、".join(channels.platform_name(c) for c in selected)))

    incoming, chosen, reports = [], [], []
    author, mid = "", ""
    result["fetched"] = 0

    # B站:官方搜索 + 同系列聚类(只有这里需要聚类;--up 可限定 UP 主)
    if "bilibili" in selected:
        log("正在搜索 B站 (最多 %d 页)..." % pages)
        items = search_bilibili(keyword, pages, verbose=False)
        result["fetched"] += len(items)
        log("共抓取 %d 条结果,正在聚类同系列..." % len(items))
        found, ranked = pick_series(items, keyword, up)
        if found:
            chosen = found
            author = up or found[0].get("author", "")
            mid = found[0].get("mid", "")
            result["author"] = author
            log("识别系列: UP主「%s」,命中 %d 期" % (author, len(found)))
            if not up and ranked:
                log("候选UP主: %s" % ", ".join("%s(%d)" % (a, c) for a, c in ranked))
            incoming.extend(normalize(v, keyword) for v in found)
            reports.append({"channel": "bilibili", "name": "B站", "found": len(found), "error": ""})
        else:
            reason = "B站未找到匹配视频(关键词需完整出现在标题中,或取消「指定UP主」再试)"
            log(reason)
            reports.append({"channel": "bilibili", "name": "B站", "found": 0, "error": reason})
    else:
        log("未选择 B站,跳过视频搜索")

    # 图文渠道:搜索引擎只用来找链接,公众号再抓正文;小红书不抓正文
    for pkey in ("wechat", "xhs"):
        if pkey not in selected:
            continue
        label = channels.platform_name(pkey)
        log("正在检索%s主题内容(搜索引擎找候选链接)..." % label)
        try:
            hits = channels.search_topic(keyword, pkey, limit=12, log=log)
        except Exception as exc:
            reason = "%s搜索失败: %s" % (label, exc)
            log(reason)
            reports.append({"channel": pkey, "name": label, "found": 0, "error": str(exc)})
            continue
        result["fetched"] += len(hits)
        picked = []
        for hit in hits:
            raw = {
                "platform": pkey, "kind": channels.platform_kind(pkey),
                "url": hit.get("url", ""), "title": hit.get("title", ""),
            }
            if pkey == "wechat":
                try:
                    raw = channels.fetch_wechat(hit["url"], log=lambda *a, **kw: None)
                except Exception as exc:
                    log("  正文抓取失败,沿用搜索标题: %s (%s)" % (hit["url"][:60], exc))
            else:
                # 小红书未登录读不到正文,用笔记 ID 做去重键,保留原文链接
                ids = re.findall(r"/(?:explore|discovery/item)/([0-9a-zA-Z]{16,})", hit.get("url", ""))
                if ids:
                    raw["key"] = "xhs:" + ids[0]
            item = article_item(raw, pkey)
            if item.get("key"):
                picked.append(item)
        log("  %s命中 %d 条,成功入库候选 %d 条" % (label, len(hits), len(picked)))
        reports.append({
            "channel": pkey, "name": label, "found": len(picked),
            "error": "" if picked else "命中的链接均无法解析,可改用「按链接采集」手工补录",
        })
        incoming.extend(picked)

    result["channel_report"] = reports
    if not incoming:
        reasons = "；".join(r["error"] for r in reports if r.get("error"))
        result["error"] = "未采集到内容。" + (reasons or "请检查关键词或更换渠道")
        log(result["error"])
        return result

    seen, incoming_unique = set(), []
    for v in incoming:
        key = item_key(v)
        if key and key not in seen:
            seen.add(key)
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
        # 内容没变,但本次的填写信息(以及可能改过的标题)仍要留痕,供下次回填
        record_intake_only(uid, intake, report, title=title, log=log)
        result["ok"] = True
        result["data_file"] = "assets/data/collections/%s.js" % uid
        result["page_file"] = "series.html?id=%s" % uid
        result["topic_count"] = len(index)
        return result

    page_path = "series.html?id=%s" % uid
    has_video = any(v.get("platform") in ("", "bilibili") and v.get("bv") for v in videos)
    if not author:
        author = next((v.get("author") for v in videos if v.get("author")), "")
        result["author"] = author
    final_slogan = slogan or (
        "共收录 %d 期,点击卡片跳转 B站观看" % len(videos) if has_video and not any(
            v.get("platform") not in ("", "bilibili") for v in videos)
        else "共收录 %d 条内容 · 点击卡片查看详情" % len(videos)
    )
    # 标签:B站系列取最新一期的正式标签(只请求 1 次);图文合集取内容自带标签,
    # 都没有时退回主题关键词,保证首页筛选有内容
    unit_tags = []
    if chosen:
        latest_raw = max(chosen, key=lambda v: v.get("pubdate", 0) or 0)
        unit_tags = fetch_video_tags(latest_raw.get("bvid", ""), log=log)
    if not unit_tags:
        counts = {}
        for v in videos:
            for tag in v.get("tags") or []:
                if tag:
                    counts[tag] = counts.get(tag, 0) + 1
        unit_tags = [t for t, _ in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)]
    if not unit_tags:
        unit_tags = [keyword]

    actual = set((v.get("platform") or "bilibili") for v in videos)
    # 按 B站 / 公众号 / 小红书的固定顺序生成渠道清单,首页可按任一渠道筛到多平台合集
    plat_order = [k for k in ("bilibili", "wechat", "xhs") if k in actual]
    plat_list = list(plat_order)  # 存稳定 key,首页按 key 筛选、前端映射中文名
    plat_key = plat_list[0] if len(plat_list) == 1 else "multi"
    plat_name = channels.platform_name(plat_key) if plat_key != "multi" else "多平台"
    if mid:
        source_url = "https://space.bilibili.com/%s/video" % mid
    else:
        source_url = next((v.get("url") for v in videos if v.get("url")), "")
    data_path, index = _finalize_unit(
        uid, "series", title, final_slogan,
        {"platform": plat_key, "name": author or plat_name, "url": source_url},
        videos, unit_tags, keyword, existing_data, intake, report, index,
        platforms=plat_list)

    result["ok"] = True
    result["data_file"] = display_path(data_path)
    result["page_file"] = page_path
    result["topic_count"] = len(index)
    log("采集完成: %s" % result["data_file"])
    log("数据单元页: %s" % page_path)
    log("采集索引: %s (共 %d 个单元,本次%s)" % (display_path(INDEX_JS), len(index), "更新" if is_update else "新建"))
    log("跳转地址: %s" % result["sample_url"])
    return result


def _backfill_item_fields(data):
    """为存量条目补齐多渠道字段(platform/kind/key),幂等"""
    changed = False
    for v in data.get("videos") or []:
        if not v.get("platform"):
            v["platform"] = "bilibili" if v.get("bv") else ""
            changed = True
        if not v.get("kind"):
            v["kind"] = "video" if v.get("bv") else "article"
            changed = True
        normalized = item_key(v)
        if normalized and v.get("key") != normalized:
            v["key"] = normalized
            changed = True
    return changed


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
                   unit_id=None, log=print, manual=None, intake=None):
    """
    按链接采集单条内容,自动识别渠道:
      - B站(含 BV 号、b23.tv 短链、视频页链接)→ 视频详情接口
      - 公众号 / 小红书 → 文章适配层解析;被风控时可传 manual 手工补录
    """
    plat = channels.detect_platform(url)
    # 没有域名但能解析出 BV 号(用户直接贴 BV 号)也算 B站
    if plat == "bilibili" or (not plat and extract_bvid(url)):
        return _collect_bilibili_single(
            url, title=title, slug=slug, slogan=slogan, dry_run=dry_run,
            unit_id=unit_id, log=log, intake=intake)
    if not plat:
        return {
            "ok": False, "keyword": url, "error":
                "无法识别该链接的渠道,目前支持 B站(bilibili.com / b23.tv)、"
                "公众号(mp.weixin.qq.com)、小红书(xiaohongshu.com / xhslink.com)",
            "added": 0, "updated": 0, "kept": 0, "total": 0, "fetched": 0,
            "data_file": "", "page_file": "", "unit_id": "", "type": "single",
        }
    return _collect_article_single(
        url, plat, title=title, slug=slug, slogan=slogan, dry_run=dry_run,
        unit_id=unit_id, log=log, manual=manual, intake=intake)


def _unit_id_from_item(item, plat, existing_ids):
    """为图文内容生成稳定可读的单元 id:公众号用短链末段,小红书用笔记 ID"""
    key = item.get("key") or ""
    tail = key.split(":", 1)[-1]
    m = re.search(r"/s/([A-Za-z0-9_-]{6,})", tail)
    if plat == "wechat" and m:
        base = "wx-" + m.group(1).lower()
    elif plat == "xhs" and re.search(r"[0-9a-fA-F]{20,}", tail):
        base = "xhs-" + re.search(r"([0-9a-fA-F]{20,})", tail).group(1).lower()
    else:
        base = "%s-%s" % (
            {"wechat": "wx", "xhs": "xhs"}.get(plat, "item"),
            hashlib.md5((item.get("url") or "").encode("utf-8")).hexdigest()[:10])
    base = re.sub(r"[^a-zA-Z0-9_-]", "", base)[:40]
    candidate, n = base, 1
    while candidate in existing_ids and candidate != base:
        n += 1
        candidate = "%s-%d" % (base, n)
    return candidate


def _collect_article_single(url, plat, title=None, slug=None, slogan=None,
                            dry_run=False, unit_id=None, log=print, manual=None,
                            intake=None):
    """采集单条图文内容(公众号/小红书),写入一个 single 单元"""
    plat_name = channels.platform_name(plat)
    result = {
        "ok": False, "keyword": url, "error": None,
        "added": 0, "updated": 0, "kept": 0, "total": 0,
        "fetched": 0, "author": "", "data_file": "", "page_file": "",
        "sample_url": "", "topic_count": 0, "unit_id": "", "type": "single",
        "platform": plat,
    }
    log("识别渠道: %s" % plat_name)
    try:
        raw = channels.fetch(url, log=log)
    except channels.PlatformError as exc:
        if (manual or {}).get("title"):
            log("抓取失败: %s" % exc)
            log("改用手工补录: %s" % manual.get("title"))
            item = manual_item(url, plat, manual)
        else:
            result["error"] = str(exc)
            log(result["error"])
            return result
    else:
        item = article_item(raw, plat)

    if not item.get("title"):
        result["error"] = "内容标题为空,无法建立单元"
        log(result["error"])
        return result

    result["fetched"] = 1
    result["author"] = item.get("author", "")
    log("标题: %s" % item["title"])
    log("作者: %s | 发布: %s" % (item.get("author") or "—", item.get("date") or "—"))
    if item.get("desc"):
        log("摘要: %s" % item["desc"][:60])

    index = load_index()
    existing_ids = {t.get("id") for t in index}
    final_title = (title or "").strip() or item["title"]
    wanted = (unit_id or slug or "").strip()
    if wanted:
        uid = re.sub(r"[^a-zA-Z0-9_-]", "", wanted) or _unit_id_from_item(item, plat, existing_ids)
    else:
        matched = next((t for t in index if t.get("title") == final_title), None)
        uid = matched["id"] if matched else _unit_id_from_item(item, plat, existing_ids)
    result["unit_id"] = uid
    is_update = uid in existing_ids

    existing_data = load_collection_data(uid)
    videos, report = merge_videos(existing_data.get("videos") if existing_data else [], [item])
    result.update(report)
    result["sample_url"] = videos[0]["url"] if videos else ""

    if dry_run:
        log("\n[dry-run] 未写文件")
        log("%s | %s | %s" % (item["url"], item["date"], item["title"]))
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
        record_intake_only(uid, intake, report, title=final_title, log=log)
        result.update(ok=True, data_file="assets/data/collections/%s.js" % uid,
                      page_file="single.html?id=%s" % uid, topic_count=len(index))
        return result

    page_path = "single.html?id=%s" % uid
    final_slogan = slogan or "单条内容精选 · 前往%s阅读原文" % plat_name
    unit_tags = item.get("tags") or guess_tags(final_title, [item.get("author") or ""])
    data_path, index = _finalize_unit(
        uid, "single", final_title, final_slogan,
        {"platform": platform_key(plat_name), "name": item.get("author") or plat_name,
         "url": item["url"]},
        videos, unit_tags, url, existing_data, intake, report, index)
    result.update(ok=True, data_file=display_path(data_path),
                  page_file=page_path, topic_count=len(index))
    log("采集完成: %s" % result["data_file"])
    log("数据单元页: %s" % page_path)
    log("采集索引: %s (共 %d 个单元,本次%s)" % (
        display_path(INDEX_JS), len(index), "更新" if is_update else "新建"))
    return result


def collect_batch(text, title=None, slug=None, slogan=None, dry_run=False,
                  unit_id=None, log=print, intake=None):
    """
    批量链接采集:一次粘贴多条链接(可混合 B站/公众号/小红书),合成一个单元。
      - 1 条成功结果按 single 处理,2 条及以上按 series(合集)处理
      - 单条失败不影响其他链接,失败原因随结果返回
    """
    result = {
        "ok": False, "keyword": "", "error": None,
        "added": 0, "updated": 0, "kept": 0, "total": 0,
        "fetched": 0, "author": "", "data_file": "", "page_file": "",
        "sample_url": "", "topic_count": 0, "unit_id": "", "type": "series",
        "platform": "", "failed": [],
    }
    urls = channels.extract_urls(text)
    if not urls:
        result["error"] = "未从文本中找到链接,请粘贴以 http(s):// 开头的原文地址,一行一条"
        return result
    log("识别到 %d 条链接" % len(urls))

    items, failed = [], []
    for u in urls:
        plat = channels.detect_platform(u)
        try:
            if plat == "bilibili" or (not plat and extract_bvid(u)):
                bvid = extract_bvid(u)
                if not bvid:
                    raise ValueError("未能解析出 BV 号")
                item = normalize(fetch_video_by_bvid(bvid, log=log), "")
            elif plat:
                item = article_item(channels.fetch(u, log=lambda m: None), plat)
            else:
                raise ValueError("暂不支持该链接")
            items.append(item)
            log("  ✓ [%s] %s" % (platform_label(item.get("platform")), item["title"][:48]))
        except Exception as exc:
            failed.append({"url": u, "error": str(exc)})
            log("  ✗ %s —— %s" % (u, str(exc)[:80]))

    result["failed"] = failed
    if not items:
        result["error"] = "全部链接都采集失败:%s" % (failed[0]["error"] if failed else "未知原因")
        log(result["error"])
        return result

    # 同一内容可能重复粘贴,按 key 去重
    unique, seen = [], set()
    for item in items:
        key = item_key(item)
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    items = unique
    result["fetched"] = len(items)

    index = load_index()
    existing_ids = {t.get("id") for t in index}
    wanted = (unit_id or slug or "").strip()
    if wanted:
        uid = re.sub(r"[^a-zA-Z0-9_-]", "", wanted) or slugify("", None, existing_ids)
    else:
        raw_title = (title or "").strip()
        matched = next((t for t in index if t.get("title") == raw_title), None) if raw_title else None
        uid = matched["id"] if matched else slugify(
            "|".join(sorted(item_key(i) for i in items)), None, existing_ids)
    result["unit_id"] = uid
    is_update = uid in existing_ids

    existing_data = load_collection_data(uid)
    videos, report = merge_videos(existing_data.get("videos") if existing_data else [], items)
    result.update(report)
    result["sample_url"] = videos[0]["url"] if videos else ""
    log("去重合并: 新增 %d / 更新 %d / 未变 %d / 合计 %d 条" % (
        report["added"], report["updated"], report["kept"], report["total"]))

    unit_type = (existing_data or {}).get("type") or ("series" if len(videos) > 1 else "single")
    result["type"] = unit_type

    if dry_run:
        log("\n[dry-run] 未写文件")
        for v in videos[:20]:
            log("%s | %s | %s" % (platform_label(v.get("platform")), v.get("date"), v.get("title")))
        result["ok"] = True
        return result

    # 渠道与来源名称:单一渠道直接显示,混合渠道标注「多平台」
    plat_keys = list(dict.fromkeys([i.get("platform") for i in items if i.get("platform")]))
    plat_label = platform_label(plat_keys[0]) if len(plat_keys) == 1 else "多平台"
    authors = list(dict.fromkeys([i.get("author") for i in items if i.get("author")]))
    if len(authors) == 1:
        source_name = authors[0]
    elif authors:
        source_name = "%s 等 %d 个来源" % (authors[0], len(authors))
    else:
        source_name = plat_label
    result["platform"] = plat_label
    result["author"] = source_name

    page_path = "%s.html?id=%s" % ("series" if unit_type == "series" else "single", uid)
    # 批量采集没填标题时,用「来源 · N 条合集」而不是笼统的「批量采集」
    default_title = (videos[0]["title"] if len(videos) == 1
                     else "%s · %d 条合集" % (source_name, len(videos)))
    final_title = (title or "").strip() or default_title
    final_slogan = slogan or "共收录 %d 条内容 · %s" % (len(videos), plat_label)

    tag_pool = []
    for item in items:
        for t in (item.get("tags") or []):
            if t not in tag_pool:
                tag_pool.append(t)
    unit_tags = tag_pool[:10] or guess_tags(final_title, [source_name])

    data_path, index = _finalize_unit(
        uid, unit_type, final_title, final_slogan,
        {"platform": platform_key(plat_label), "name": source_name,
         "url": items[0].get("url", "")},
        videos, unit_tags, "batch", existing_data, intake, report, index,
        platforms=plat_keys)
    result.update(ok=True, data_file=display_path(data_path),
                  page_file=page_path, topic_count=len(index))
    log("采集完成: %s" % result["data_file"])
    log("数据单元页: %s" % page_path)
    if failed:
        log("失败 %d 条(已跳过,不影响成功项)" % len(failed))
    log("采集索引: %s (共 %d 个单元,本次%s)" % (
        display_path(INDEX_JS), len(index), "更新" if is_update else "新建"))
    return result


def _collect_bilibili_single(url, title=None, slug=None, slogan=None, dry_run=False,
                             unit_id=None, log=print, intake=None):
    """按 B站 视频链接采集单条视频,写入一个 single 单元。来源是视频详情 API。"""
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
        record_intake_only(uid, intake, report, title=final_title, log=log)
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
    data_path, index = _finalize_unit(
        uid, "single", final_title, final_slogan,
        {"platform": "bilibili", "name": video["author"],
         "url": ("https://space.bilibili.com/%s/video" % raw.get("mid"))
                if raw.get("mid") else video["url"]},
        videos, unit_tags, url, existing_data, intake, report, index)

    result["ok"] = True
    result["data_file"] = display_path(data_path)
    result["page_file"] = page_path
    result["topic_count"] = len(index)
    log("采集完成: %s" % result["data_file"])
    log("数据单元页: %s" % page_path)
    log("采集索引: %s (共 %d 个单元,本次%s)" % (display_path(INDEX_JS), len(index), "更新" if is_update else "新建"))
    log("跳转地址: %s" % result["sample_url"])
    return result


def normalize_dataset(log=print, dry_run=False):
    """D24 数据侧解耦(幂等):
    1. 去掉数据与索引里的 page 字段(路由由前端按 type 推导);
    2. source.platform / platforms 统一为稳定 key(bilibili/wechat/xhs/multi)。
    返回 {"ok", "units", "changed"}。
    """
    index = load_index()
    changed_units = 0
    index_changed = False

    for meta in index:
        if "page" in meta:
            meta.pop("page")
            index_changed = True
        src = meta.get("source")
        if isinstance(src, dict) and "platform" in src:
            key = platform_key(src.get("platform"))
            if key != src.get("platform"):
                src["platform"] = key
                index_changed = True
        plats = meta.get("platforms")
        if isinstance(plats, list):
            new = [platform_key(x) for x in plats]
            if new != plats:
                meta["platforms"] = new
                index_changed = True

        uid = meta.get("id")
        if not uid:
            continue
        data = load_collection_data(uid)
        if not data:
            continue
        dirty = False
        if "page" in data:
            data.pop("page")
            dirty = True
        src = data.get("source")
        if isinstance(src, dict) and "platform" in src:
            key = platform_key(src.get("platform"))
            if key != src.get("platform"):
                src["platform"] = key
                dirty = True
        plats = data.get("platforms")
        if isinstance(plats, list):
            new = [platform_key(x) for x in plats]
            if new != plats:
                data["platforms"] = new
                dirty = True
        if dirty:
            changed_units += 1
            if not dry_run:
                write_collection_file(data)

    if index_changed and not dry_run:
        write_index(index, datetime.date.today().isoformat())
    log("归一完成: %d 个单元有改动%s" % (changed_units, "(预览,未写盘)" if dry_run else ""))
    return {"ok": True, "units": len(index), "changed": changed_units}


def build_parser():
    parser = argparse.ArgumentParser(
        description="多渠道采集数据生成器: B站(视频) / 公众号(图文) / 小红书(图文),纯规则不使用 AI,不生成页面")
    parser.add_argument("keyword", nargs="?", default=None, help="搜索主题关键词(或 --url 时的链接/BV号)")
    parser.add_argument("--pages", type=int, default=30, help="搜索翻页数,默认30(每页20条)")
    parser.add_argument("--title", default=None, help="显示标题")
    parser.add_argument("--up", default=None, help="限定UP主名称")
    parser.add_argument("--id", dest="unit_id", default=None, help="采集单元 id;命中已有单元则只更新它")
    parser.add_argument("--slug", default=None, help="同 --id,兼容旧参数")
    parser.add_argument("--slogan", default=None, help="副标题")
    parser.add_argument("--channels", default=None,
                        help="按主题采集的渠道,逗号分隔:bilibili,wechat,xhs(默认 bilibili)")
    parser.add_argument("--url", action="store_true", help="按链接采集单条内容(自动识别 B站/公众号/小红书)")
    parser.add_argument("--batch", action="store_true", help="批量链接采集:位置参数传多条链接/分享文案")
    parser.add_argument("--manual-title", default=None, help="手工补录标题(抓取被风控时使用)")
    parser.add_argument("--manual-author", default=None, help="手工补录作者/公众号名")
    parser.add_argument("--manual-desc", default=None, help="手工补录摘要")
    parser.add_argument("--manual-date", default=None, help="手工补录发布日期(如 2025-04-09)")
    parser.add_argument("--manual-cover", default=None, help="手工补录封面图地址")
    parser.add_argument("--dry-run", action="store_true", help="只预览不写文件")
    parser.add_argument("--list", action="store_true", help="列出所有采集单元")
    parser.add_argument("--normalize", action="store_true",
                        help="数据侧解耦:去掉 page 字段,platform 统一为稳定 key(幂等)")
    parser.add_argument("--verify", action="store_true",
                        help="数据一致性自检(索引/数据文件/count/key/日期/开关),有问题返回非 0")
    parser.add_argument("--toggle", metavar="ID", default=None, help="开启/关闭某单元显示,配合 --on/--off")
    parser.add_argument("--on", dest="toggle_on", action="store_true", help="配合 --toggle:开启显示")
    parser.add_argument("--off", dest="toggle_off", action="store_true", help="配合 --toggle:关闭显示")
    parser.add_argument("--topics", action="append", default=None, metavar="FILE",
                        help="按主题清单批量采集(如 topics.yml),可多次指定以合并清单")
    return parser


def _yaml_value(raw):
    """解析 topics.yml 里的标量:去引号、去行内注释(引号内的 # 不当作注释)"""
    value = raw.strip()
    if not value:
        return ""
    if value[0] in ('"', "'"):
        quote = value[0]
        end = value.find(quote, 1)
        if end > 0:
            return value[1:end]
        return value[1:]
    # 无引号时,空格后的 # 视为注释
    for idx, ch in enumerate(value):
        if ch == "#" and idx > 0 and value[idx - 1].isspace():
            value = value[:idx].rstrip()
            break
    return value


def load_topics_yaml(path):
    """解析 topics.yml 的受限子集(不引入 PyYAML,保持零依赖)

    支持的结构:
        topics:
          - keyword: "关键词"      # 必填,精准匹配标题
            id: daily-website      # 可选,命中已有单元则续采该单元
            title: "显示标题"       # 可选
            channels: [bilibili, wechat, xhs]   # 可选,默认 bilibili
    不支持嵌套、多行字符串、锚点等高级语法;解析失败会明确报行号。
    """
    entries = []
    current = None
    started = False
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.rstrip(":") == "topics" and not line.startswith(" "):
            started = True
            continue
        if stripped.startswith("- "):
            if not started:
                raise ValueError("%s:%d 列表项必须位于 topics: 之下" % (path, lineno))
            if current:
                entries.append(current)
            current = {}
            item = stripped[2:].strip()
            if item:
                if ":" not in item:
                    raise ValueError("%s:%d 无法解析列表项: %s" % (path, lineno, item))
                key, raw = item.split(":", 1)
                current[key.strip()] = _yaml_value(raw)
            continue
        if not started:
            raise ValueError("%s:%d 无法识别的内容: %s" % (path, lineno, stripped))
        if current is None or ":" not in stripped:
            raise ValueError("%s:%d 无法解析字段: %s" % (path, lineno, stripped))
        key, raw = stripped.split(":", 1)
        current[key.strip()] = _yaml_value(raw)
    if current:
        entries.append(current)

    result = []
    for idx, item in enumerate(entries, 1):
        keyword = (item.get("keyword") or "").strip()
        if not keyword:
            raise ValueError("%s:第 %d 个主题缺少 keyword" % (path, idx))
        channel_list = item.get("channels") or "bilibili"
        if isinstance(channel_list, str):
            channel_list = [c.strip() for c in channel_list.strip("[]").split(",") if c.strip()]
        unknown = [c for c in channel_list if c not in channels_valid()]
        if unknown:
            raise ValueError("%s:第 %d 个主题的渠道不支持: %s(可选 %s)" % (
                path, idx, ", ".join(unknown), ", ".join(channels_valid())))
        result.append({
            "keyword": keyword,
            "id": (item.get("id") or "").strip() or None,
            "title": (item.get("title") or "").strip() or None,
            "channels": channel_list,
        })
    return result


def channels_valid():
    return list(channels.PLATFORMS.keys())


def run_topics(paths, pages=30, dry_run=False, log=print):
    """按 topics.yml 批量采集:逐个主题调用 collect_topic,单条失败不影响其余"""
    entries = []
    for path in paths:
        if not os.path.exists(path):
            print("错误:主题清单不存在: %s" % path, file=sys.stderr)
            return {"ok": False, "error": "主题清单不存在: %s" % path}
        try:
            entries.extend(load_topics_yaml(path))
        except ValueError as exc:
            print("错误:%s" % exc, file=sys.stderr)
            return {"ok": False, "error": str(exc)}
    if not entries:
        return {"ok": False, "error": "主题清单为空"}

    log("按主题清单采集:共 %d 个主题" % len(entries))
    failed = []
    for idx, item in enumerate(entries, 1):
        log("")
        log("=== [%d/%d] %s ===" % (idx, len(entries), item["keyword"]))
        try:
            result = collect_topic(
                keyword=item["keyword"], pages=pages, title=item["title"],
                unit_id=item["id"], dry_run=dry_run, log=log,
                topic_channels=item["channels"],
            )
        except Exception as exc:
            log("采集失败: %s" % exc)
            failed.append({"keyword": item["keyword"], "error": str(exc)})
            continue
        if not result.get("ok"):
            failed.append({"keyword": item["keyword"], "error": result.get("error", "未知错误")})
    if failed:
        log("")
        log("完成,但 %d 个主题失败:" % len(failed))
        for f in failed:
            log("  - %s: %s" % (f["keyword"], f["error"]))
        return {"ok": False, "failed": failed}
    log("")
    log("全部 %d 个主题采集完成" % len(entries))
    return {"ok": True}


def main():
    args = build_parser().parse_args()

    if args.normalize:
        r = normalize_dataset(dry_run=args.dry_run)
        sys.exit(0 if r["ok"] else 1)
    if args.verify:
        r = verify_data()
        print("自检%s" % ("通过" if r["ok"] else "未通过"))
        sys.exit(0 if r["ok"] else 1)
    if args.list:
        for t in load_index():
            mark = "on " if t.get("enabled", True) else "off"
            print("[%s] %-10s %-14s %s (%s 条)" % (
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

    if args.topics:
        r = run_topics(args.topics, pages=args.pages, dry_run=args.dry_run)
        if not r["ok"]:
            sys.exit(1)
        return

    if not args.keyword:
        print("错误:请提供主题关键词/链接,或使用 --list/--toggle/--verify", file=sys.stderr)
        sys.exit(1)

    manual = {
        "title": args.manual_title, "author": args.manual_author,
        "desc": args.manual_desc, "date": args.manual_date, "cover": args.manual_cover,
    }
    # 命令行采集也记录本次填写信息,与网页采集共用同一份回填数据
    intake = normalize_intake({
        "mode": "batch" if args.batch else ("url" if args.url else "keyword"),
        "input": args.keyword,
        "title": args.title or "",
        "up": args.up or "",
        "pages": args.pages,
        "channels": args.channels,
        "manual_title": args.manual_title, "manual_author": args.manual_author,
        "manual_desc": args.manual_desc, "manual_date": args.manual_date,
        "manual_cover": args.manual_cover,
    })
    if args.batch:
        result = collect_batch(
            text=args.keyword, title=args.title, slug=args.slug,
            slogan=args.slogan, dry_run=args.dry_run, unit_id=args.unit_id,
            intake=intake,
        )
    elif args.url:
        result = collect_by_url(
            url=args.keyword, title=args.title, slug=args.slug,
            slogan=args.slogan, dry_run=args.dry_run, unit_id=args.unit_id,
            manual=manual, intake=intake,
        )
    else:
        result = collect_topic(
            keyword=args.keyword, pages=args.pages, title=args.title, up=args.up,
            slug=args.slug, slogan=args.slogan, dry_run=args.dry_run, unit_id=args.unit_id,
            topic_channels=args.channels, intake=intake,
        )
    if not result["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
