#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集页 · 多渠道适配层

只做一件事:把各平台的内容链接解析成统一结构,交给 generate.py 去合并、去重、写数据。
纯 HTTP 请求 + 固定正则规则,不使用浏览器自动化,也不调用任何 AI。

支持的渠道:
  bilibili  B站     视频 / 播放页(解析由 generate.py 的视频接口负责,这里只做识别)
  wechat    公众号   图文文章(抓取文章页,解析标题、公众号名、封面、摘要、发布时间)
  xhs       小红书   图文笔记 / 视频笔记(解析分享链接;被风控时抛出可操作提示)

统一结构(各适配器返回值):
  {
    "platform": "wechat", "kind": "article",
    "key": "wechat:<唯一标识>",      # 去重键,跨平台唯一
    "url": "https://...",           # 干净的原文地址
    "title": "...", "author": "...", "source_name": "...",
    "cover": "https://...", "desc": "...",
    "date": "2025.04.09", "ts": 1744166119,
  }
"""

import datetime
import html
import json
import re
import sys
import urllib.parse
import urllib.request

UA_DESKTOP = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")
UA_MOBILE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
             "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

# 平台元信息:名称用于页面展示,kind 区分视频/图文,color 用于徽标配色
PLATFORMS = {
    "bilibili": {"name": "B站", "kind": "video", "color": "#fb7299"},
    "wechat": {"name": "公众号", "kind": "article", "color": "#07c160"},
    "xhs": {"name": "小红书", "kind": "article", "color": "#ff2442"},
}

# 平台识别规则:域名 → 平台标识
_HOST_RULES = [
    ("bilibili", ("bilibili.com", "b23.tv")),
    ("wechat", ("mp.weixin.qq.com", "weixin.qq.com")),
    ("xhs", ("xiaohongshu.com", "xhslink.com")),
]

_URL_RE = re.compile(r"https?://[^\s，。、；;\"'<>（）()【】\[\]]+", re.I)


class PlatformError(Exception):
    """抓取失败:message 会直接展示给用户,需带可操作提示"""


def detect_platform(url):
    """从链接识别平台标识,无法识别返回空字符串"""
    host = urllib.parse.urlparse((url or "").strip()).netloc.lower()
    if not host:
        return ""
    for key, domains in _HOST_RULES:
        for d in domains:
            if host == d or host.endswith("." + d):
                return key
    return ""


def platform_name(key):
    return (PLATFORMS.get(key) or {}).get("name", key or "")


def platform_kind(key):
    return (PLATFORMS.get(key) or {}).get("kind", "article")


def extract_urls(text):
    """
    从多行文本/分享文案中提取所有链接,保持出现顺序并去重。
    支持一行一条,也支持一条文案里夹带链接。
    """
    found, seen = [], set()
    for raw in _URL_RE.findall(text or ""):
        url = raw.strip().rstrip(".,;:!?)）】」》")
        # 分享链接常见的尾巴标记
        url = url.split("#")[0]
        if not url or url in seen:
            continue
        seen.add(url)
        found.append(url)
    return found


def _get(url, headers=None, timeout=25):
    """发请求,返回 (最终地址, 文本)。自动跟随跳转,便于处理短链"""
    req = urllib.request.Request(url, headers=headers or {"User-Agent": UA_DESKTOP})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        final = resp.geturl()
        raw = resp.read()
    # 微信/小红书页面均为 UTF-8;个别老页面为 GBK,解码失败时回退
    for enc in ("utf-8", "gbk"):
        try:
            return final, raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return final, raw.decode("utf-8", "ignore")


def _unixtime_to_date(ts):
    """时间戳(秒)按东八区转 yyyy.mm.dd,与站点日期格式一致"""
    try:
        ts = int(float(ts))
    except Exception:
        return "", 0
    if ts <= 0:
        return "", 0
    dt = datetime.datetime.fromtimestamp(ts, datetime.timezone(datetime.timedelta(hours=8)))
    return dt.strftime("%Y.%m.%d"), ts


def _meta_content(text, prop):
    """读取 <meta property="og:xxx" content="...">;属性顺序不固定,两种都试"""
    pats = [
        r'<meta[^>]+property=["\']%s["\'][^>]*content=["\']([^"\']*)["\']' % re.escape(prop),
        r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*property=["\']%s["\']' % re.escape(prop),
    ]
    for p in pats:
        m = re.search(p, text, re.I)
        if m:
            return html.unescape(m.group(1)).strip()
    return ""


def _js_var(text, name):
    """读取 var name = '...' / var name = htmlDecode("...") 形式的字符串变量"""
    pat = r"var\s+%s\s*=\s*(?:htmlDecode\()?\s*(['\"])(.*?)\1" % re.escape(name)
    m = re.search(pat, text, re.S)
    if not m:
        return ""
    return html.unescape(m.group(2)).strip()


def _strip_tags(text):
    text = re.sub(r"<script[\s\S]*?</script>", " ", text or "", flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------- 公众号

def fetch_wechat(url, log=print):
    """
    抓取公众号文章页。文章页正文内嵌了标题/公众号名/封面/摘要/发布时间等变量,
    直接用固定正则读取,无需登录。返回统一结构。
    """
    clean = url.split("#")[0]
    headers = {
        "User-Agent": UA_DESKTOP,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    final, text = _get(clean, headers)
    if "参数错误" in text and "msg_title" not in text:
        raise PlatformError("公众号链接不完整或已失效,请重新复制文章链接(形如 https://mp.weixin.qq.com/s/xxxx)")
    if "该内容已被发布者删除" in text or "此内容因违规无法查看" in text:
        raise PlatformError("该公众号文章已被删除或无法查看")

    title = _meta_content(text, "og:title") or _js_var(text, "msg_title")
    # 标题偶尔带「- 微信公众平台」后缀
    title = re.sub(r"\s*[-_]\s*微信公众平台\s*$", "", title).strip()
    source_name = _js_var(text, "nickname") or _meta_content(text, "og:article:author")
    author = _js_var(text, "author") or source_name
    cover = _js_var(text, "msg_cdn_url") or _meta_content(text, "og:image")
    desc = _meta_content(text, "og:description") or _js_var(text, "msg_desc")
    if not desc:
        m = re.search(r'<div[^>]+id="js_content"[^>]*>([\s\S]*?)</div>\s*<script', text)
        if m:
            desc = _strip_tags(m.group(1))
    if cover.startswith("//"):
        cover = "https:" + cover

    ts = _js_var(text, "ct") or _js_var(text, "create_time")
    if not ts:
        m = re.search(r'var\s+ct\s*=\s*"(\d+)"', text)
        ts = m.group(1) if m else ""
    date, stamp = _unixtime_to_date(ts)

    if not title:
        raise PlatformError("未能解析出公众号文章标题,请确认链接是否为已发布文章")
    return {
        "platform": "wechat",
        "kind": "article",
        "key": "wechat:" + clean,
        "url": clean,
        "title": title,
        "author": author,
        "source_name": source_name or author,
        "cover": cover,
        "desc": desc[:160],
        "date": date or "—",
        "ts": stamp,
    }


# ---------------------------------------------------------------- 小红书

_XHS_ID_RE = re.compile(r"/(?:explore|discovery/item|item)/([0-9a-fA-F]{20,32})")


def extract_xhs_id(url):
    m = _XHS_ID_RE.search(url or "")
    return m.group(1) if m else ""


def _xhs_state(text):
    """取出页面内嵌的 __INITIAL_STATE__(含 undefined 字面量,先替换再解析)"""
    m = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{[\s\S]*?\})\s*</script>", text)
    if not m:
        return None
    raw = m.group(1)
    raw = re.sub(r"\bundefined\b", "null", raw)
    try:
        return json.loads(raw)
    except Exception:
        return None


def _xhs_find_note(node, depth=0):
    """在状态树里找笔记对象(不同版本字段位置会变,按特征递归查找)"""
    if depth > 8:
        return None
    if isinstance(node, dict):
        if ("noteId" in node or "id" in node) and ("desc" in node or "title" in node) and "user" in node:
            return node
        for value in node.values():
            found = _xhs_find_note(value, depth + 1)
            if found:
                return found
    elif isinstance(node, list):
        for item in node[:20]:
            found = _xhs_find_note(item, depth + 1)
            if found:
                return found
    return None


def _xhs_cover(note):
    for img in (note.get("imageList") or []):
        if not isinstance(img, dict):
            continue
        for key in ("urlDefault", "urlPre", "url", "traceId"):
            if img.get(key):
                return img[key]
    video = note.get("video") or {}
    if isinstance(video, dict):
        image = video.get("image") or {}
        if isinstance(image, dict) and image.get("firstFrame"):
            return image["firstFrame"]
    return ""


def fetch_xhs(url, log=print):
    """
    抓取小红书笔记。分享链接(xhslink.com)会先跟随跳转拿到带 xsec_token 的完整地址。
    未登录 + 无 token 时平台会跳转 404 页,此时抛出 PlatformError 提示改用分享链接或手工补录。
    """
    clean = url.split("#")[0]
    headers = {
        "User-Agent": UA_DESKTOP,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://www.xiaohongshu.com/",
    }
    try:
        final, text = _get(clean, headers)
    except Exception as exc:
        raise PlatformError("小红书请求失败: %s" % exc)

    if "/404/" in final or "当前笔记暂时无法浏览" in text:
        raise PlatformError(
            "小红书拒绝了本次抓取(笔记页需要带 xsec_token 的分享链接,且链接有时效)。"
            "请在 App 内「分享 → 复制链接」后立即重试;或填写标题使用「手工补录」。")

    state = _xhs_state(text)
    note = _xhs_find_note(state) if state else None
    if not note:
        raise PlatformError(
            "未能从页面解析出笔记内容(小红书对未登录访问有风控)。"
            "请改用 App 内「分享 → 复制链接」得到的 xhslink 链接;或填写标题使用「手工补录」。")

    note_id = str(note.get("noteId") or note.get("id") or extract_xhs_id(final) or "")
    title = (note.get("title") or "").strip() or (note.get("desc") or "").strip().split("\n")[0]
    desc = (note.get("desc") or "").strip()
    user = note.get("user") or {}
    author = (user.get("nickname") or user.get("nickName") or "").strip() if isinstance(user, dict) else ""
    cover = _xhs_cover(note)
    stamp = note.get("time") or note.get("lastUpdateTime") or 0
    try:
        stamp = int(stamp)
        if stamp > 10 ** 11:  # 毫秒
            stamp = stamp // 1000
    except Exception:
        stamp = 0
    date, ts = _unixtime_to_date(stamp)

    if not title:
        raise PlatformError("该小红书笔记没有可用标题,请填写标题后使用「手工补录」")

    # 链接保留 xsec_token(等价于原分享凭证),便于用户从站点回跳到原笔记
    final_url = final if "xiaohongshu.com" in final else clean
    return {
        "platform": "xhs",
        "kind": "video" if note.get("type") == "video" else "article",
        "key": "xhs:" + (note_id or final_url),
        "url": final_url.split("#")[0],
        "title": title[:120],
        "author": author,
        "source_name": author,
        "cover": cover,
        "desc": desc[:160],
        "date": date or "—",
        "ts": ts,
    }


# ---------------------------------------------------------------- 按主题搜索
# 公众号 / 小红书没有公开关键词搜索接口(搜狗微信已拦截、小红书需登录),
# 只能借助搜索引擎的 site: 检索拿到候选链接;正文仍走各平台自己的解析器。
# 结果仅用于「按主题采集」,数量与相关性都取决于搜索引擎,失败要如实告诉用户。

_SEARCH_SITES = {
    "wechat": {"site": "site:mp.weixin.qq.com", "hosts": ("mp.weixin.qq.com",)},
    "xhs": {"site": "site:xiaohongshu.com", "hosts": ("xiaohongshu.com",)},
}

# 各渠道按优先级尝试多个搜索引擎:任一拿到候选链接即停,全部失败才报错。
# 搜索引擎会间歇性风控,单点依赖不可靠;这里只找链接,绝不把搜索摘要当正文。
_SEARCH_ENGINES = {
    "wechat": [
        {"name": "百度移动", "query": "https://m.baidu.com/s?word=%s&from=1000050b", "ua": UA_MOBILE, "parser": "baidu_mobile"},
        {"name": "百度网页", "query": "https://www.baidu.com/s?wd=%s", "ua": UA_DESKTOP, "parser": "baidu_web"},
        {"name": "搜狗网页", "query": "https://www.sogou.com/web?query=%s", "ua": UA_DESKTOP, "parser": "sogou"},
    ],
    "xhs": [
        {"name": "360搜索", "query": "https://www.so.com/s?q=%s", "ua": UA_DESKTOP, "parser": "so360"},
        {"name": "百度移动", "query": "https://m.baidu.com/s?word=%s&from=1000050b", "ua": UA_MOBILE, "parser": "baidu_mobile"},
        {"name": "百度网页", "query": "https://www.baidu.com/s?wd=%s", "ua": UA_DESKTOP, "parser": "baidu_web"},
    ],
}


def _search_host_ok(url, hosts):
    netloc = urllib.parse.urlparse(url).netloc.lower()
    return any(netloc == h or netloc.endswith("." + h) for h in hosts)


def _clean_search_title(text):
    title = re.sub(r"<[^>]+>", "", html.unescape(text or ""))
    title = re.sub(r"\s+", " ", title).strip()
    # 搜索引擎常把站点名拼在标题尾部
    title = re.sub(r"\s*[-|｜—]\s*(小红书|微信公众号)$", "", title)
    return title.strip()


def _parse_search_page(platform_key, parser, page):
    """从搜索结果页提取 (url, title);不同搜索引擎 DOM 不同,按类型解析"""
    cfg = _SEARCH_SITES[platform_key]
    hosts = cfg["hosts"]
    pairs = []

    def add(url, block):
        url = html.unescape(url or "").replace("\\", "").strip()
        if not _search_host_ok(url, hosts):
            return
        h3 = re.search(r"<h3[^>]*>(.*?)</h3>", block or "", re.S)
        title = _clean_search_title(h3.group(1) if h3 else "")
        if platform_key == "xhs":
            # 跳过学校/助手等非笔记页;去掉 xsec_token,同一篇笔记不会重复入库
            if not re.search(r"/(?:explore|discovery/item)/[0-9a-zA-Z]{16,}", url):
                return
            if not title:
                return
            parts = urllib.parse.urlsplit(url)
            url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        pairs.append((url, title))

    if parser == "baidu_mobile":
        # 每个 c-result 块的 data-log 里带 mu="<原文直链>",标题在同块 h3
        for block in re.split(r'<div\s+class="c-result result"', page)[1:]:
            m = re.search(r'[\\"]mu[\\"]:\s*[\\"]?(https?://[^\\"\']+)', block)
            if m:
                add(m.group(1), block)
    elif parser == "baidu_web":
        # 桌面版结果块上的 mu="<原文直链>",标题在其后的 h3
        mus = list(re.finditer(r'mu="(https?://[^"]+)"', page))
        for i, m in enumerate(mus):
            end = mus[i + 1].start() if i + 1 < len(mus) else min(len(page), m.end() + 6000)
            add(m.group(1), page[m.end():end])
    elif parser == "so360":
        # 360 结果的 data-mdurl 是原文直链,标题在同一个 res-list 块的 h3
        for block in re.split(r'<li class="res-list', page)[1:]:
            m = re.search(r'data-mdurl="(https?://[^"]+)"', block)
            if m:
                add(m.group(1), block)
    elif parser == "sogou":
        for url in _URL_RE.findall(page):
            if not _search_host_ok(html.unescape(url), hosts):
                continue
            idx = page.find(url)
            add(url, page[max(0, idx - 1500):idx + 600])

    seen, out = set(), []
    for url, title in pairs:
        if not url or url in seen:
            continue
        seen.add(url)
        out.append({"url": url, "title": title})
    return out


def search_topic(keyword, platform_key, limit=20, log=print):
    """
    按关键词检索某图文渠道的候选内容,返回 [{"url","title","engine"}]。
    只找链接;公众号正文请用 fetch_wechat 再抓,小红书以搜索标题为准。
    搜索引擎会间歇性风控,按顺序尝试多个引擎,全部失败才抛 PlatformError。
    """
    cfg = _SEARCH_SITES.get(platform_key)
    if not cfg:
        raise PlatformError("渠道 %s 不支持按主题搜索" % platform_key)
    keyword = (keyword or "").strip()
    if not keyword:
        raise PlatformError("主题关键词不能为空")

    errors = []
    for engine in _SEARCH_ENGINES[platform_key]:
        url = engine["query"] % urllib.parse.quote("%s %s" % (cfg["site"], keyword))
        try:
            _, page = _get(url, headers={
                "User-Agent": engine["ua"], "Accept-Language": "zh-CN,zh;q=0.9",
            }, timeout=15)
        except Exception as exc:
            errors.append("%s请求失败" % engine["name"])
            continue
        if "百度安全验证" in page or "请输入验证码" in page:
            errors.append("%s触发安全验证" % engine["name"])
            continue
        hits = _parse_search_page(platform_key, engine["parser"], page)
        if not hits:
            errors.append("%s无结果" % engine["name"])
            continue

        # 按标题与关键词的重合度排序,减少搜索引擎的噪声结果
        tokens = [t for t in re.split(r"[\s|｜/、,，:：\-—_()（）\[\]【】#]+", keyword) if len(t) >= 2]
        def score(hit):
            title = hit.get("title", "").lower()
            return sum(1 for t in tokens if t.lower() in title) + (1 if keyword.lower() in title else 0)
        ranked = sorted(hits, key=score, reverse=True)
        matched = [h for h in ranked if score(h) > 0]
        if not matched:
            log("  %s返回的标题未直接包含关键词,已按原始顺序收录,请自行核对" % engine["name"])
            matched = ranked
        for hit in matched[:limit]:
            hit["engine"] = engine["name"]
        if errors:
            log("  搜索兜底: %s" % "、".join(errors))
        return matched[:limit]

    raise PlatformError("%s主题搜索失败(%s),请稍后重试或改用「按链接采集」" % (
        platform_name(platform_key), "；".join(errors) or "无可用搜索引擎"))


# ---------------------------------------------------------------- 统一入口

def fetch(url, log=print):
    """按链接自动识别渠道并解析;B站交给 generate.py 的视频接口处理"""
    key = detect_platform(url)
    if key == "wechat":
        return fetch_wechat(url, log=log)
    if key == "xhs":
        return fetch_xhs(url, log=log)
    if key == "bilibili":
        raise PlatformError("B站链接请使用视频详情接口解析")
    raise PlatformError("暂不支持该链接,目前可采集 B站 / 公众号 / 小红书的公开内容")
