"""数据层回归(D13/D14):索引解析、原子写入、一致性自检、CLI 冒烟。不联网。
运行: python3 -m unittest discover -s tests
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "collector"))

TMP = tempfile.mkdtemp(prefix="jiye-test-")
os.environ["VIDEO_DATA_DIR"] = TMP  # 必须在 import generate 之前设置

import generate  # noqa: E402


def unit_js(uid, videos, enabled=True, section="tools"):
    data = {"id": uid, "type": "series", "title": "测试单元 " + uid,
            "section": section,
            "count": len(videos), "videos": videos}
    if enabled is not None:
        data["enabled"] = enabled
    return "window.COLLECTION_DATA[%s] = %s;\n" % (json.dumps(uid), json.dumps(data, ensure_ascii=False))


def write_unit(uid, videos, enabled=True):
    path = os.path.join(generate.COLLECTIONS_DIR, uid + ".js")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(unit_js(uid, videos, enabled))
    return path


def video(i, date=None):
    date = date or ("2026.11.%02d" % (i + 1))
    return {"title": "条目 %d" % i, "key": "k%d" % i, "bv": "BV1test%04d" % i,
            "url": "https://www.bilibili.com/video/BV1test%04d/" % i, "date": date}


class GenerateDataTest(unittest.TestCase):
    def setUp(self):
        for name in os.listdir(TMP):
            path = os.path.join(TMP, name)
            shutil.rmtree(path, ignore_errors=True) if os.path.isdir(path) else os.remove(path)
        os.makedirs(generate.COLLECTIONS_DIR, exist_ok=True)

    def write_index(self, items):
        for item in items:
            item.setdefault("section", "tools")
        generate.write_index(items, "2026-11-26")

    def test_site_config_validate_and_roundtrip(self):
        cfg = generate.normalize_site_config({
            "default_layout": "magazine",
            "display": {"visible_layouts": ["standard", "news", "magazine"],
                        "visible_themes": ["default", "dark", "tech", "campus", "classical"]},
            "editorial": {"u1": {"pin": True, "pin_at": "2026-11-27 10:00",
                                 "hero_image": "https://example.com/a.jpg"}}
        }, {"u1"})
        self.assertEqual(cfg["default_layout"], "magazine")
        self.assertTrue(cfg["editorial"]["u1"]["pin"])
        self.assertEqual(cfg["display"]["visible_themes"][-1], "classical")
        path = os.path.join(TMP, "site.yml")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(generate.dump_site_yaml(cfg))
        self.assertEqual(generate.load_site_config(path), cfg)
        self.assertEqual(generate.build_site_payload(cfg), {
            "default_layout": "magazine",
            "display": {"visible_layouts": ["standard", "news", "magazine"],
                        "visible_themes": ["default", "dark", "tech", "campus", "classical"],
                        "max_layouts": 5, "max_themes": 5},
            "editorial": cfg["editorial"]})
        empty = generate.normalize_site_config({"default_layout": "standard", "editorial": {}})
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(generate.dump_site_yaml(empty))
        self.assertEqual(generate.load_site_config(path), empty)

    def test_site_config_rejects_bad_values(self):
        for raw in (
            {"default_layout": "unknown"},
            {"default_layout": "standard", "editorial": {"nope": {"pin": True, "pin_at": "2026-11-27 10:00"}}},
            {"default_layout": "standard", "editorial": {"u1": {"pin": True, "pin_at": "2026-11-27"}}},
            {"default_layout": "standard", "editorial": {"u1": {"hero_image": "javascript:alert(1)"}}},
            {"default_layout": "standard", "editorial": {"u1": {"pin": "yes", "pin_at": "2026-11-27 10:00"}}},
            {"default_layout": "standard", "display": {"visible_layouts": []}},
            {"default_layout": "standard", "display": {"visible_layouts": ["news"]}},
            {"default_layout": "standard", "display": {"visible_layouts": ["standard", "standard"]}},
            {"default_layout": "standard", "display": {"visible_themes": ["default", "dark", "tech", "campus", "classical", "anime"]}},
            {"default_layout": "news", "display": {"visible_layouts": ["standard"]}},
        ):
            with self.assertRaises(ValueError):
                generate.normalize_site_config(raw, {"u1"})

    def test_site_config_allows_loopback_http(self):
        cfg = generate.normalize_site_config({"editorial": {"u1": {"hero_image": "http://127.0.0.1:8000/a.jpg"}}}, {"u1"})
        self.assertEqual(cfg["editorial"]["u1"]["hero_image"], "http://127.0.0.1:8000/a.jpg")

    def test_server_unit_page_routes(self):
        import server
        self.assertEqual(server.unit_page({"id": "a", "type": "single"}), "single.html?id=a")
        self.assertEqual(server.unit_page({"id": "b"}), "series.html?id=b")

    def test_server_is_threaded(self):
        import socketserver
        import server
        self.assertTrue(issubclass(server.ReusableTCPServer, socketserver.ThreadingMixIn))

    def test_index_sorted_by_last_at_desc(self):
        items = [
            {"id": "old", "type": "single", "count": 1, "last_at": "2026-11-25 08:00", "updated": "2026-11-25"},
            {"id": "new", "type": "series", "count": 2, "last_at": "2026-11-26 16:50", "updated": "2026-11-26"},
            {"id": "mid", "type": "single", "count": 1, "last_at": "2026-11-26 09:42", "updated": "2026-11-26"},
            {"id": "legacy", "type": "single", "count": 1, "updated": "2026-11-24"},
        ]
        self.write_index(items)
        self.assertEqual([t["id"] for t in generate.load_index()], ["new", "mid", "old", "legacy"])

    def test_season_records_from_view_payload(self):
        x = {"owner": {"name": "默认作者"}, "ugc_season": {
            "title": "测试合集", "sections": [{"title": "第一节", "episodes": [
                {"bvid": "BV1aa", "title": "第一集", "arc": {
                    "title": "第一集", "pic": "//i0.hdslb.com/a.jpg", "pubdate": 1744472674,
                    "duration": 402, "stat": {"view": 1163419},
                    "author": {"name": "作者甲"}, "desc": "简介"}},
                {"bvid": "BV1bb", "title": "第二集", "arc": {
                    "title": "第二集", "pic": "http://i0.hdslb.com/b.jpg", "pubdate": 1744559074},
                    "pages": [{"page": 1, "part": "上", "duration": 60, "cid": 1},
                              {"page": 2, "part": "下", "duration": 61, "cid": 2}]}
            ]}]}}
        items = generate.bili_season_records(x)
        self.assertEqual([i["key"] for i in items], ["bilibili:BV1aa", "bilibili:BV1bb"])
        self.assertEqual(items[0]["cover"], "https://i0.hdslb.com/a.jpg")
        self.assertEqual(items[0]["author"], "作者甲")
        self.assertEqual(items[0]["views"], "1163419")
        self.assertEqual(len(items[1]["parts"]), 2)

    def test_missing_index_is_not_corrupt(self):
        self.assertEqual(generate.load_index(strict=True), [])
        self.assertTrue(generate.index_status()["ok"] is False)
        self.assertIn("不存在", generate.index_status()["reason"])

    def test_corrupt_index_raises(self):
        with open(generate.INDEX_JS, "w", encoding="utf-8") as fh:
            fh.write("window.COLLECTION_INDEX = [broken;\n")
        with self.assertRaises(generate.IndexCorrupt):
            generate.load_index(strict=True)

    def test_verify_ok(self):
        write_unit("u1", [video(0), video(1)])
        self.write_index([{"id": "u1", "count": 2, "enabled": True, "type": "series"}])
        r = generate.verify_data(log=lambda *a: None)
        self.assertTrue(r["ok"], r["problems"])
        self.assertEqual(r["units"], 1)

    def test_verify_count_mismatch(self):
        write_unit("u1", [video(0)])
        self.write_index([{"id": "u1", "count": 2, "enabled": True}])
        r = generate.verify_data(log=lambda *a: None)
        self.assertFalse(r["ok"])
        self.assertTrue(any("count" in p for p in r["problems"]))

    def test_verify_duplicate_key(self):
        v = video(0)
        write_unit("u1", [v, dict(v, title="重复 key")])
        self.write_index([{"id": "u1", "count": 2, "enabled": True}])
        r = generate.verify_data(log=lambda *a: None)
        self.assertFalse(r["ok"])
        self.assertTrue(any("key 重复" in p for p in r["problems"]))

    def test_verify_bad_date(self):
        write_unit("u1", [video(0, date="2026/11/01")])
        self.write_index([{"id": "u1", "count": 1, "enabled": True}])
        r = generate.verify_data(log=lambda *a: None)
        self.assertFalse(r["ok"])
        self.assertTrue(any("日期格式" in p for p in r["problems"]))

    def test_verify_orphan_file(self):
        write_unit("ghost", [video(0)])
        self.write_index([])
        r = generate.verify_data(log=lambda *a: None)
        self.assertFalse(r["ok"])
        self.assertTrue(any("未登记" in p for p in r["problems"]))

    def test_verify_enabled_mismatch(self):
        write_unit("u1", [video(0)], enabled=True)
        self.write_index([{"id": "u1", "count": 1, "enabled": False}])
        r = generate.verify_data(log=lambda *a: None)
        self.assertFalse(r["ok"])
        self.assertTrue(any("开关" in p for p in r["problems"]))

    def test_verify_unknown_theme(self):
        # 单元级 theme 字段(D32):只做提示与校验,不启用渲染分支
        data = {"id": "u1", "type": "series", "title": "主题单元", "count": 1,
                "section": "tools", "theme": "magazine", "videos": [video(0)]}
        with open(os.path.join(generate.COLLECTIONS_DIR, "u1.js"), "w", encoding="utf-8") as fh:
            fh.write("window.COLLECTION_DATA[\"u1\"] = %s;\n" % json.dumps(data, ensure_ascii=False))
        self.write_index([{"id": "u1", "count": 1, "enabled": True}])
        r = generate.verify_data(log=lambda *a: None)
        self.assertFalse(r["ok"])
        self.assertTrue(any("theme 取值" in p for p in r["problems"]))

    def test_write_text_atomic_no_tmp_left(self):
        path = os.path.join(TMP, "atomic.txt")
        generate.write_text_atomic(path, "hello")
        self.assertEqual(open(path, encoding="utf-8").read(), "hello")
        self.assertFalse(os.path.exists(path + ".tmp"))

    def test_write_index_snapshot(self):
        self.write_index([{"id": "u1", "count": 0}])
        self.write_index([{"id": "u1", "count": 0, "title": "改过"}])
        snaps = [f for f in os.listdir(generate.BACKUP_DIR) if f.startswith("index-")]
        self.assertTrue(snaps, "覆盖索引前应留快照")
        self.assertLessEqual(len(snaps), generate.SNAPSHOT_KEEP)


    def test_platform_key_mapping(self):
        self.assertEqual(generate.platform_key("B站"), "bilibili")
        self.assertEqual(generate.platform_key("公众号"), "wechat")
        self.assertEqual(generate.platform_key("小红书"), "xhs")
        self.assertEqual(generate.platform_key("多平台"), "multi")
        self.assertEqual(generate.platform_key("bilibili"), "bilibili")
        self.assertEqual(generate.platform_key(""), "bilibili")
        self.assertEqual(generate.platform_key("未知"), "未知")

    def test_verify_flags_legacy_page_and_platform(self):
        path = write_unit("u1", [video(0)])
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("window.COLLECTION_DATA[\"u1\"] = %s;\n" % json.dumps({
                "id": "u1", "type": "series", "title": "旧单元", "count": 1,
                "section": "tools",
                "page": "series.html?id=u1", "platforms": ["B站"],
                "source": {"platform": "B站"}, "videos": [video(0)]}, ensure_ascii=False))
        self.write_index([{"id": "u1", "count": 1, "enabled": True, "type": "series",
                           "page": "series.html?id=u1", "source": {"platform": "B站"}}])
        r = generate.verify_data(log=lambda *a: None)
        self.assertFalse(r["ok"])
        self.assertTrue(any("page" in p for p in r["problems"]), r["problems"])
        self.assertTrue(any("platform" in p for p in r["problems"]), r["problems"])

    def test_normalize_strips_page_and_keys_platform(self):
        path = write_unit("u1", [video(0)])
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("window.COLLECTION_DATA[\"u1\"] = %s;\n" % json.dumps({
                "id": "u1", "type": "series", "title": "旧单元", "count": 1,
                "section": "tools",
                "page": "series.html?id=u1", "platforms": ["B站", "公众号"],
                "source": {"platform": "多平台"}, "videos": [video(0)]}, ensure_ascii=False))
        self.write_index([{"id": "u1", "count": 1, "enabled": True, "type": "series",
                           "page": "series.html?id=u1", "source": {"platform": "B站"}}])
        r = generate.normalize_dataset(log=lambda *a: None)
        self.assertEqual(r["changed"], 1)
        data = generate.load_collection_data("u1")
        self.assertNotIn("page", data)
        self.assertEqual(data["platforms"], ["bilibili", "wechat"])
        self.assertEqual(data["source"]["platform"], "multi")
        meta = generate.load_index()[0]
        self.assertNotIn("page", meta)
        self.assertEqual(meta["source"]["platform"], "bilibili")
        self.assertTrue(generate.verify_data(log=lambda *a: None)["ok"])
        # 幂等:再跑一次不改动
        self.assertEqual(generate.normalize_dataset(log=lambda *a: None)["changed"], 0)

    def test_normalize_unknown_date_to_empty(self):
        """未知日期不再写「—」占位,避免 --verify/CI 被单条脏日期卡住。"""
        self.assertEqual(generate.normalize_date("—"), "")
        self.assertEqual(generate.normalize_date("2025-4-9"), "2025.04.09")
        write_unit("u2", [video(0, date="—")])
        self.write_index([{"id": "u2", "count": 1, "enabled": True, "type": "series",
                           "source": {"platform": "bilibili"}}])
        self.assertEqual(generate.normalize_dataset(log=lambda *a: None)["changed"], 1)
        self.assertEqual(generate.load_collection_data("u2")["videos"][0]["date"], "")
        self.assertTrue(generate.verify_data(log=lambda *a: None)["ok"])


    def test_finalize_unit_writes_contract(self):
        """D15:采集单元收口统一组装字段,不再各拼一份 dict"""
        index = []
        data_path, index = generate._finalize_unit(
            "u9", "series", "统一收口", "副标题",
            {"platform": "bilibili", "name": "作者", "url": ""},
            [video(0), video(1)], ["标签甲", "标签乙"], "关键词",
            None, None, {"added": 2, "updated": 0, "kept": 0, "total": 2}, index,
            platforms=["bilibili"])
        data = generate.load_collection_data("u9")
        self.assertEqual(data["type"], "series")
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["tags"], ["标签甲", "标签乙"])
        self.assertEqual(data["platforms"], ["bilibili"])
        self.assertNotIn("page", data)
        self.assertEqual(len(index), 1)
        self.assertTrue(os.path.exists(data_path))

    def test_finalize_unit_section_is_optional(self):
        """板块可留空表示未分类;选定板块时必须写入数据文件。"""
        index = []
        generate._finalize_unit(
            "u-empty", "single", "未分类", "副标题",
            {"platform": "bilibili", "name": "作者", "url": ""},
            [video(0)], ["标签"], "关键词",
            None, None, {"added": 1, "updated": 0, "kept": 0, "total": 1}, index)
        self.assertNotIn("section", generate.load_collection_data("u-empty"))
        generate._finalize_unit(
            "u-tools", "series", "工具合集", "副标题",
            {"platform": "bilibili", "name": "作者", "url": ""},
            [video(1)], ["标签"], "关键词",
            None, None, {"added": 1, "updated": 0, "kept": 0, "total": 1},
            generate.load_index(), section="tools")
        self.assertEqual(generate.load_collection_data("u-tools")["section"], "tools")

    def test_update_unit_meta_only_touches_metadata(self):
        """编辑信息只改标题/板块/标签/显示,不碰 videos,也不重新采集。"""
        write_unit("meta1", [video(0), video(1)])
        generate.rebuild_index()
        before = generate.load_collection_data("meta1")
        r = generate.update_unit_meta(
            "meta1", title="改过的标题", section="", tags=["AI", "AI", "工具"],
            enabled=False)
        self.assertTrue(r["ok"])
        data = generate.load_collection_data("meta1")
        self.assertEqual(data["title"], "改过的标题")
        self.assertEqual(data["tags"], ["AI", "工具"])
        self.assertNotIn("section", data)
        self.assertFalse(data["enabled"])
        self.assertEqual(data["videos"], before["videos"])
        item = next(t for t in generate.load_index() if t["id"] == "meta1")
        self.assertEqual(item["title"], "改过的标题")
        self.assertEqual(item["count"], 2)
        self.assertFalse(item["enabled"])
        bad = generate.update_unit_meta("meta1", section="not-a-section")
        self.assertFalse(bad["ok"])
        self.assertIn("板块不存在", bad["error"])

    def test_title_match_is_exact_keyword(self):
        """D16:匹配只做「关键词完整出现在标题」,死参数已移除"""
        self.assertTrue(generate.title_match("跟着动画学古文:第 1 集", "跟着动画学古文"))
        self.assertFalse(generate.title_match("古文动画合集", "跟着动画学古文"))


    def test_rebuild_index_from_units(self):
        """索引只是派生缓存:期数/标题/开关/创建日期都以单元文件为准"""
        data = {"id": "u1", "type": "series", "title": "文件里的标题", "count": 99,
                "section": "tools",
                "videos": [video(0), video(1)], "enabled": False,
                "updated": "2026-11-20", "intake": {"at": "2026-11-20 10:00", "mode": "url"}}
        with open(os.path.join(generate.COLLECTIONS_DIR, "u1.js"), "w", encoding="utf-8") as fh:
            fh.write("window.COLLECTION_DATA[\"u1\"] = %s;\n" % json.dumps(data, ensure_ascii=False))
        self.write_index([{"id": "u1", "title": "旧标题", "count": 1, "enabled": True,
                           "created": "2026-11-01", "updated": "2026-11-01"}])
        items = generate.rebuild_index()
        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertEqual(it["title"], "文件里的标题")
        self.assertEqual(it["count"], 2)
        self.assertEqual(it["enabled"], False)
        self.assertEqual(it["created"], "2026-11-01")
        self.assertEqual(it["updated"], "2026-11-20")
        self.assertEqual(it["last_at"], "2026-11-20 10:00")

    def test_valid_unit_id_whitelist(self):
        self.assertTrue(generate.valid_unit_id("bv1uks66oeeh"))
        self.assertTrue(generate.valid_unit_id("topic-4e6ee53f"))
        for bad in ("../x", "a/b", "a.js", "", "x" * 81):
            self.assertFalse(generate.valid_unit_id(bad))
        self.assertIsNone(generate.load_collection_data("../index"))

    def test_remove_links_from_existing_unit(self):
        """按链接重新采集时可把输入链接当作移除项;记录移除但不改原 intake"""
        data = {
            "id": "rmtest", "type": "series", "title": "待整理合集", "section": "tools",
            "count": 2, "videos": [video(0), video(1)],
            "intake": {"mode": "batch", "input": "旧输入", "at": "2026-11-20 10:00"},
            "runs": [{"at": "2026-11-20 10:00", "mode": "batch", "total": 2}],
        }
        with open(os.path.join(generate.COLLECTIONS_DIR, "rmtest.js"), "w", encoding="utf-8") as fh:
            fh.write("window.COLLECTION_DATA[\"rmtest\"] = %s;\n" % json.dumps(data, ensure_ascii=False))
        generate.rebuild_index()
        res = generate.remove_links(
            "https://www.bilibili.com/video/BV1test0000/?share=1", "rmtest", mode="url")
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["removed"], 1)
        self.assertEqual(res["total"], 1)
        got = generate.load_collection_data("rmtest")
        self.assertEqual([v["key"] for v in got["videos"]], ["k1"])
        self.assertEqual(got["intake"], data["intake"])
        self.assertEqual(got["runs"][0]["mode"], "remove")
        self.assertEqual(got["runs"][0]["removed"], 1)

    def test_remove_links_batch_and_rejects_keyword(self):
        data = {
            "id": "rmtest2", "type": "series", "title": "待整理合集二", "section": "tools",
            "count": 2, "videos": [video(0), video(1)],
        }
        with open(os.path.join(generate.COLLECTIONS_DIR, "rmtest2.js"), "w", encoding="utf-8") as fh:
            fh.write("window.COLLECTION_DATA[\"rmtest2\"] = %s;\n" % json.dumps(data, ensure_ascii=False))
        generate.rebuild_index()
        res = generate.remove_links(
            "https://www.bilibili.com/video/BV1test0000/\nhttps://www.bilibili.com/video/BV1test0001/",
            "rmtest2", mode="batch")
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["removed"], 2)
        self.assertEqual(res["total"], 0)
        self.assertEqual(generate.load_collection_data("rmtest2")["videos"], [])
        bad = generate.remove_links("任意关键词", "rmtest2", mode="keyword")
        self.assertFalse(bad["ok"])
        self.assertIn("按单元主题采集不支持", bad["error"])

    def test_slugify_reuse_for_batch_rerun(self):
        uid = generate.slugify("bilibili:BV1|wechat:abc", None, set())
        self.assertEqual(generate.slugify("bilibili:BV1|wechat:abc", None, {uid}, reuse=True), uid)
        self.assertNotEqual(generate.slugify("bilibili:BV1|wechat:abc", None, {uid}), uid)

    def test_normalize_intake_truncates_tail(self):
        raw = {"mode": "batch", "input": "A" * 4000 + "B" * 8000}
        got = generate.normalize_intake(raw)
        self.assertTrue(got["input"].startswith("…(更早内容已截断"))
        self.assertTrue(got["input"].endswith("B" * 8000))

class SectionsTopicsTest(unittest.TestCase):
    """板块注册表与混合关键词（P0 附录 2/3）。"""

    def _write(self, name, text):
        path = os.path.join(TMP, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_sections_reserved_ranges(self):
        sections = generate.load_sections_yaml()
        by_id = {s["id"]: s for s in sections}
        self.assertEqual((by_id["infant-care"]["age_min_months"], by_id["infant-care"]["age_max_months"]), (0, 36))
        self.assertEqual((by_id["preschool"]["age_min_months"], by_id["preschool"]["age_max_months"]), (36, 72))
        self.assertEqual((by_id["k12"]["age_min_months"], by_id["k12"]["age_max_months"]), (72, 216))
        self.assertFalse(by_id["humanities"]["enabled"])

    def test_sections_reject_gap(self):
        path = self._write("bad-sections.yml", """
version: 1
sections:
  - id: infant-care
    title: 婴幼儿
    age_min_months: 0
    age_max_months: 30
    order: 1
    enabled: true
  - id: preschool
    title: 学前
    age_min_months: 36
    age_max_months: 72
    order: 2
    enabled: true
  - id: k12
    title: 中小学
    age_min_months: 72
    age_max_months: 216
    order: 3
    enabled: true
""")
        with self.assertRaises(ValueError):
            generate.load_sections_yaml(path)

    def test_topics_v2_parses_must_any(self):
        path = self._write("topics-v2.yml", """
version: 1
topics:
  - id: infant-feeding
    section: infant-care
    title: 喂养与睡眠
    must_keywords: ["婴幼儿", "喂养"]
    any_keywords: ["辅食", "母乳", "配方奶"]
    channels: [bilibili]
    enabled: true
""")
        got = generate.load_topics_yaml(path)
        self.assertEqual(got[0]["must_keywords"], ["婴幼儿", "喂养"])
        self.assertEqual(got[0]["any_keywords"], ["辅食", "母乳", "配方奶"])
        self.assertEqual(got[0]["section"], "infant-care")
        self.assertEqual(got[0]["keyword"], "婴幼儿")

    def test_keyword_match_mixed(self):
        self.assertTrue(generate.keyword_match("婴幼儿喂养：辅食添加", ["婴幼儿", "喂养"], ["辅食"]))
        self.assertFalse(generate.keyword_match("婴幼儿睡眠", ["婴幼儿", "喂养"], ["辅食"]))
        self.assertTrue(generate.keyword_match("ＳｐｒｉｎｇＡＩ 教程", ["springai"]))
        self.assertFalse(generate.keyword_match("Spring 教程", ["springai"]))

    def test_preferred_author_blocks_series_drift(self):
        items = [
            {"title": "每天挖掘一个神奇网站：A", "author": "新作者"},
            {"title": "每天挖掘一个神奇网站：B", "author": "原作者"},
        ]
        found, ranked, report = generate.pick_series_multi(
            items, ["每天挖掘一个神奇网站"], [], preferred_author="原作者")
        self.assertEqual([x["author"] for x in found], ["原作者"])
        self.assertTrue(report["preferred_locked"])
        # 原作者没有命中时宁可本次不更新，也不切换到其他作者
        found, _, report = generate.pick_series_multi(
            items, ["每天挖掘一个神奇网站"], [], preferred_author="不存在的作者")
        self.assertEqual(found, [])
        self.assertTrue(report["preferred_miss"])

    def test_run_topics_partial_keeps_ok(self):
        path = self._write("topics-run.yml", """
version: 1
topics:
  - id: one
    section: tools
    title: 成功
    must_keywords: ["成功"]
    channels: [bilibili]
    enabled: true
  - id: two
    section: tools
    title: 失败
    must_keywords: ["失败"]
    channels: [bilibili]
    enabled: true
""")
        old = generate.collect_topic
        def fake(**kwargs):
            if kwargs["unit_id"] == "two":
                return {"ok": False, "error": "模拟失败"}
            return {"ok": True}
        generate.collect_topic = fake
        try:
            r = generate.run_topics([path], log=lambda *a: None)
        finally:
            generate.collect_topic = old
        self.assertTrue(r["ok"])
        self.assertEqual(r["status"], "partial")
        self.assertEqual(len(r["failed"]), 1)


class CliSmokeTest(unittest.TestCase):
    """在真实仓库数据上跑 CLI(只读)"""

    def run_cli(self, *args):
        env = {k: v for k, v in os.environ.items() if k != "VIDEO_DATA_DIR"}
        return subprocess.run([sys.executable, "collector/generate.py", *args],
                              cwd=ROOT, capture_output=True, text=True, timeout=120, env=env)

    def test_list(self):
        r = self.run_cli("--list")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("daily-website", r.stdout)

    def test_merge_for_mode(self):
        """D55:append 保留旧条目;replace 只保留本次,并报告 removed"""
        old = [{"key": "bilibili:BV1", "title": "旧1"}, {"key": "bilibili:BV2", "title": "旧2"}]
        new = [{"key": "bilibili:BV1", "title": "新1"}, {"key": "bilibili:BV3", "title": "新3"}]
        merged, rep = generate.merge_for_mode(old, new, replace=False)
        self.assertEqual(rep["added"], 1)
        self.assertEqual(len(merged), 3)
        merged2, rep2 = generate.merge_for_mode(old, new, replace=True)
        self.assertEqual(len(merged2), 2)
        self.assertEqual([v["key"] for v in merged2], ["bilibili:BV1", "bilibili:BV3"])
        self.assertEqual(rep2["removed"], 2)
        self.assertEqual(rep2["total"], 2)

    def test_bili_parts_and_season(self):
        """B站详情扩展:多P才返回分P目录;合集展平分节"""
        single = {"pages": [{"page": 1, "part": "唯一P", "duration": 10}]}
        self.assertEqual(generate.bili_parts(single), [])
        multi = {"pages": [{"page": 1, "part": "P1", "duration": 320, "cid": 1},
                           {"page": 2, "part": "P2", "duration": 21, "cid": 2}]}
        parts = generate.bili_parts(multi)
        self.assertEqual([p["p"] for p in parts], [1, 2])
        self.assertEqual(parts[1]["title"], "P2")
        self.assertIsNone(generate.bili_season({"ugc_season": None}))
        season = {"ugc_season": {"title": "合集A", "sections": [
            {"title": "第一节", "episodes": [{"bvid": "BV1aa", "title": "第一集",
                                            "arc": {"duration": 61}}]}]}}
        got = generate.bili_season(season)
        self.assertEqual(got["title"], "合集A")
        self.assertEqual(got["episodes"][0]["bvid"], "BV1aa")
        self.assertEqual(got["episodes"][0]["duration"], 61)
        self.assertEqual(got["episodes"][0]["section"], "第一节")

    def test_verify_real_data(self):
        r = self.run_cli("--verify")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("自检通过", r.stdout)


class CollectTopicAccountTest(unittest.TestCase):
    """按单元主题采集:指定账号只对 B站 / 公众号生效,小红书明确忽略。"""

    def setUp(self):
        self._search = generate.channels.search_topic
        self._fetch = generate.channels.fetch_wechat
        self.logs = []

    def tearDown(self):
        generate.channels.search_topic = self._search
        generate.channels.fetch_wechat = self._fetch

    def logs_text(self):
        return "\n".join(str(x) for x in self.logs)

    def test_account_match(self):
        self.assertTrue(generate.account_match("草根的异世界", "草根的异世界"))
        # 平台昵称常带后缀,归一化后按前缀匹配
        self.assertTrue(generate.account_match("草根的异世界 · 官方", "草根的异世界"))
        self.assertFalse(generate.account_match("别家公众号", "草根的异世界"))
        # 抓不到账号名时不允许放过
        self.assertFalse(generate.account_match("", "草根的异世界"))

    def test_wechat_up_filters_by_account(self):
        hits = [{"url": "https://mp.weixin.qq.com/s/a"},
                {"url": "https://mp.weixin.qq.com/s/b"},
                {"url": "https://mp.weixin.qq.com/s/c"}]

        def fake_search(keyword, platform_key, limit=20, log=print, account=None):
            self.assertEqual(platform_key, "wechat")
            self.assertEqual(account, "草根的异世界")
            return hits

        def fake_fetch(url, log=print):
            if url.endswith("/a"):
                return {"platform": "wechat", "kind": "article", "url": url,
                        "title": "每日一站 第1期", "author": "草根的异世界",
                        "source_name": "草根的异世界", "date": "2026-11-20"}
            if url.endswith("/b"):
                return {"platform": "wechat", "kind": "article", "url": url,
                        "title": "每日一站 第2期", "author": "别家公众号",
                        "source_name": "别家公众号", "date": "2026-11-21"}
            raise ValueError("正文抓取失败")

        generate.channels.search_topic = fake_search
        generate.channels.fetch_wechat = fake_fetch
        res = generate.collect_topic("每日一站", pages=1, title="账号限定单元",
                                     up="草根的异世界", dry_run=True,
                                     topic_channels=["wechat"], log=self.logs.append,
                                     unit_id="acct-test")
        self.assertTrue(res["ok"])
        self.assertEqual(res["added"], 1)
        self.assertIn("跳过 2 条", self.logs_text())

    def test_xhs_ignores_up_with_notice(self):
        def fake_search(keyword, platform_key, limit=20, log=print, account=None):
            self.assertEqual(platform_key, "xhs")
            self.assertIsNone(account)
            return [{"url": "https://www.xiaohongshu.com/explore/0123456789abcdef01234567",
                     "title": "每日一站 第1篇"}]

        generate.channels.search_topic = fake_search
        res = generate.collect_topic("每日一站", up="某个账号", dry_run=True,
                                     topic_channels=["xhs"], log=self.logs.append,
                                     unit_id="xhs-acct-test")
        self.assertTrue(res["ok"])
        self.assertEqual(res["added"], 1)
        self.assertIn("小红书不支持按账号限定", self.logs_text())


if __name__ == "__main__":
    unittest.main()
