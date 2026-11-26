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


def unit_js(uid, videos, enabled=True):
    data = {"id": uid, "type": "series", "title": "测试单元 " + uid,
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
        generate.write_index(items, "2026-11-26")

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
                "theme": "magazine", "videos": [video(0)]}
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

    def test_title_match_is_exact_keyword(self):
        """D16:匹配只做「关键词完整出现在标题」,死参数已移除"""
        self.assertTrue(generate.title_match("跟着动画学古文:第 1 集", "跟着动画学古文"))
        self.assertFalse(generate.title_match("古文动画合集", "跟着动画学古文"))


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


if __name__ == "__main__":
    unittest.main()
