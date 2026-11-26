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

    def test_verify_real_data(self):
        r = self.run_cli("--verify")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("自检通过", r.stdout)


if __name__ == "__main__":
    unittest.main()
