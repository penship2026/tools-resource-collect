#!/usr/bin/env python3
"""A4 工作台测试：批准前零变化、事务回滚、管理处 5 套/锁定、HTTP 冒烟。"""
import hashlib
import json
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "ai-template"))

import cli  # noqa: E402
import site_store  # noqa: E402

publish = cli.publish
display = cli.display
server = cli.server
THEME_SPEC = json.loads((ROOT / "tests" / "fixtures" / "specs" / "theme-mist.json").read_text(encoding="utf-8"))
LAYOUT_SPEC = json.loads((ROOT / "tests" / "fixtures" / "specs" / "layout-news-dense.json").read_text(encoding="utf-8"))

LAYOUT_JS = '''window.TEMPLATES = {
  list: {
    "standard": {"file": "standard.css", "label": "简洁"},
    "news": {"file": "news.css", "label": "门户"},
    "magazine": {"file": "magazine.css", "label": "画册"},
    /* AI_LAYOUTS */
  },
};
'''
THEME_JS = '''window.THEMES = {
  "default": {"file": "default.css", "label": "浅色"},
  "dark": {"file": "dark.css", "label": "深色"},
  "tech": {"file": "tech.css", "label": "科技"},
  "campus": {"file": "campus.css", "label": "学院"},
  "classical": {"file": "classical.css", "label": "古典"},
  "anime": {"file": "anime.css", "label": "二次元"},
  /* AI_THEMES */
};
'''
SITE_YML = '''version: 1

site:
  name: 测试站
  default_layout: standard

editorial:
  picks:
    - one
'''
SITE_JS = '''window.SITE_CONFIG = {"default_layout": "standard", "site": {"name": "测试站"}};
window.EDITORIAL = {"picks": ["one"], "nested": {"a": 1}};
'''


def make_root():
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    (root / "assets").mkdir()
    (root / "assets" / "templates.js").write_text(LAYOUT_JS, encoding="utf-8")
    (root / "assets" / "theme.js").write_text(THEME_JS, encoding="utf-8")
    (root / "site.yml").write_text(SITE_YML, encoding="utf-8")
    (root / "assets" / "site.js").write_text(SITE_JS, encoding="utf-8")
    (root / "tools" / "ai-template").mkdir(parents=True)
    (root / "tools" / "ai-template" / "published.json").write_text(
        json.dumps({"layouts": {}, "themes": {}}, ensure_ascii=False), encoding="utf-8")
    return tmp, root


def add_candidate(root, key="mist-a4", visual=True, gates_ok=True, spec_base=THEME_SPEC):
    folder = root / "tools" / "ai-template" / "drafts" / key / "candidate-1"
    folder.mkdir(parents=True)
    spec = dict(spec_base)
    spec["key"] = key
    spec["name"] = "测试设计"
    (folder / "spec.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    gates = [{"gate": "G%d" % i, "ok": gates_ok, "code": "G%d_X" % i, "message": "test"}
             for i in range(1, 7)]
    metrics = {"ok": bool(gates_ok), "visual": "checked" if visual else "skipped",
               "gates": gates, "metrics": {"cssBytes": 1000, "shots": 15}}
    (folder / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False), encoding="utf-8")
    return folder / "spec.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ApproveTest(unittest.TestCase):
    def test_reviewer_required_before_any_asset_change(self):
        tmp, root = make_root()
        self.addCleanup(tmp.cleanup)
        spec = add_candidate(root)
        before = {p: digest(p) for p in (root / "assets" / "templates.js", root / "assets" / "theme.js")}
        with self.assertRaises(publish.PublishError) as ctx:
            publish.approve_candidate(spec, "", root=root)
        self.assertEqual(ctx.exception.code, "APPROVE_REVIEWER")
        after = {p: digest(p) for p in (root / "assets" / "templates.js", root / "assets" / "theme.js")}
        self.assertEqual(before, after)
        self.assertFalse((root / "assets" / "themes" / "mist-a4.css").exists())

    def test_gate_and_visual_required(self):
        tmp, root = make_root()
        self.addCleanup(tmp.cleanup)
        bad_gates = add_candidate(root, "bad-gates", visual=True, gates_ok=False)
        with self.assertRaises(publish.PublishError) as ctx:
            publish.approve_candidate(bad_gates, "liyan", root=root)
        self.assertEqual(ctx.exception.code, "APPROVE_GATES_FAILED")
        bad_visual = add_candidate(root, "bad-visual", visual=False, gates_ok=True)
        with self.assertRaises(publish.PublishError) as ctx:
            publish.approve_candidate(bad_visual, "liyan", root=root)
        self.assertEqual(ctx.exception.code, "APPROVE_VISUAL_UNVERIFIED")

    def test_approve_writes_registry_docs_review_not_site(self):
        tmp, root = make_root()
        self.addCleanup(tmp.cleanup)
        spec = add_candidate(root)
        site_yml = digest(root / "site.yml")
        site_js = digest(root / "assets" / "site.js")
        result = publish.approve_candidate(spec, "liyan", root=root, model="mock", prompt_id="test")
        self.assertTrue(result["ok"])
        self.assertTrue((root / "assets" / "themes" / "mist-a4.css").exists())
        self.assertTrue((root / "docs" / "templates" / "mist-a4.json").exists())
        self.assertTrue((root / "docs" / "templates" / "mist-a4.md").exists())
        self.assertTrue((root / result["review"]).exists())
        self.assertIn('"mist-a4":', (root / "assets" / "theme.js").read_text(encoding="utf-8"))
        published = json.loads((root / "tools" / "ai-template" / "published.json").read_text(encoding="utf-8"))
        entry = published["themes"]["mist-a4"]
        self.assertEqual(entry["source"], "AI")
        self.assertEqual(entry["file"], "assets/themes/mist-a4.css")
        self.assertEqual(site_yml, digest(root / "site.yml"))
        self.assertEqual(site_js, digest(root / "assets" / "site.js"))
        with self.assertRaises(publish.PublishError) as ctx:
            publish.approve_candidate(spec, "liyan", root=root)
        self.assertEqual(ctx.exception.code, "PUBLISH_EXISTS")

    def test_layout_approve_writes_templates_registry(self):
        tmp, root = make_root()
        self.addCleanup(tmp.cleanup)
        spec = add_candidate(root, "news-a4", spec_base=LAYOUT_SPEC)
        before_theme = digest(root / "assets" / "theme.js")
        result = publish.approve_candidate(spec, "liyan", root=root)
        self.assertTrue(result["ok"])
        self.assertTrue((root / "assets" / "layouts" / "news-a4.css").exists())
        self.assertIn('"news-a4":', (root / "assets" / "templates.js").read_text(encoding="utf-8"))
        published = json.loads((root / "tools" / "ai-template" / "published.json").read_text(encoding="utf-8"))
        self.assertEqual(published["layouts"]["news-a4"]["file"], "assets/layouts/news-a4.css")
        self.assertEqual(before_theme, digest(root / "assets" / "theme.js"))

    def test_transaction_rollback_keeps_draft_and_runtime(self):
        tmp, root = make_root()
        self.addCleanup(tmp.cleanup)
        spec = add_candidate(root)
        before_theme = digest(root / "assets" / "theme.js")
        before_pub = digest(root / "tools" / "ai-template" / "published.json")
        original = publish._atomic_write
        calls = [0]

        def flaky(path, content):
            calls[0] += 1
            if calls[0] == 4:
                raise OSError("模拟写失败")
            return original(path, content)

        publish._atomic_write = flaky
        try:
            with self.assertRaises(publish.PublishError) as ctx:
                publish.approve_candidate(spec, "liyan", root=root)
        finally:
            publish._atomic_write = original
        self.assertEqual(ctx.exception.code, "PUBLISH_FAILED")
        self.assertTrue(spec.exists())
        self.assertFalse((root / "assets" / "themes" / "mist-a4.css").exists())
        self.assertFalse((root / "docs" / "templates" / "mist-a4.json").exists())
        self.assertEqual(before_theme, digest(root / "assets" / "theme.js"))
        self.assertEqual(before_pub, digest(root / "tools" / "ai-template" / "published.json"))


class RejectReviseTest(unittest.TestCase):
    def test_reject_and_revise_limit(self):
        tmp, root = make_root()
        self.addCleanup(tmp.cleanup)
        spec = add_candidate(root, "reject-a4")
        result = publish.reject_candidate(spec, "liyan", "同质化", "太像 news", root=root)
        self.assertTrue(result["ok"])
        record = json.loads((root / result["review"]).read_text(encoding="utf-8"))
        self.assertEqual(record["decision"], "rejected")
        self.assertEqual(record["reason"], "同质化")
        self.assertFalse((root / "assets" / "themes" / "reject-a4.css").exists())
        with self.assertRaises(publish.PublishError) as ctx:
            publish.reject_candidate(spec, "liyan", "不喜欢", root=root)
        self.assertEqual(ctx.exception.code, "REJECT_REASON")

        spec2 = add_candidate(root, "rev-a4")
        first = publish.record_revision(spec2, "首轮意见", "liyan", root=root)
        second = publish.record_revision(spec2, "二轮意见", "liyan", root=root)
        self.assertEqual((first["round"], second["round"]), (1, 2))
        with self.assertRaises(publish.PublishError) as ctx:
            publish.record_revision(spec2, "第三轮", "liyan", root=root)
        self.assertEqual(ctx.exception.code, "REVISE_LIMIT")


class DisplayTest(unittest.TestCase):
    def test_limit_can_expand_to_show_more_than_five(self):
        tmp, root = make_root()
        self.addCleanup(tmp.cleanup)
        result = display.set_limit("theme", 8, root=root)
        self.assertTrue(result["ok"])
        self.assertEqual(site_store.read_display(root)["max_themes"], 8)
        self.assertIn('"max_themes": 8', (root / "assets" / "site.js").read_text(encoding="utf-8"))
        self.assertTrue(display.set_visible("theme", "anime", True, root=root)["changed"])
        visible = site_store.read_display(root)
        self.assertEqual(len(visible["visible_themes"]), 6)
        self.assertIn("anime", visible["visible_themes"])
        with self.assertRaises(display.DisplayError) as ctx:
            display.set_limit("theme", 3, root=root)
        self.assertEqual(ctx.exception.code, "DISPLAY_LIMIT_TOO_SMALL")

    def test_five_slot_lock_and_editorial_preserved(self):
        tmp, root = make_root()
        self.addCleanup(tmp.cleanup)
        payload = display.manage_payload(root)
        self.assertEqual(payload["kinds"]["layout"]["count"], 3)
        self.assertEqual(payload["kinds"]["theme"]["count"], 5)
        standard = next(item for item in payload["kinds"]["layout"]["items"] if item["key"] == "standard")
        self.assertTrue(standard["locked"])

        with self.assertRaises(display.DisplayError) as ctx:
            display.set_visible("theme", "anime", True, root=root)
        self.assertEqual(ctx.exception.code, "DISPLAY_FULL")
        with self.assertRaises(display.DisplayError) as ctx:
            display.set_visible("theme", "default", False, root=root)
        self.assertEqual(ctx.exception.code, "DISPLAY_LOCKED")
        with self.assertRaises(display.DisplayError) as ctx:
            display.set_visible("theme", "ghost", True, root=root)
        self.assertEqual(ctx.exception.code, "DISPLAY_UNKNOWN")

        self.assertTrue(display.set_visible("theme", "dark", False, root=root)["changed"])
        self.assertTrue(display.set_visible("theme", "anime", True, root=root)["changed"])
        visible = site_store.read_display(root)
        self.assertNotIn("dark", visible["visible_themes"])
        self.assertIn("anime", visible["visible_themes"])
        self.assertEqual(len(visible["visible_themes"]), 5)
        yml = (root / "site.yml").read_text(encoding="utf-8")
        self.assertIn("display:", yml)
        self.assertIn("editorial:", yml)
        self.assertIn("picks:", yml)
        js = (root / "assets" / "site.js").read_text(encoding="utf-8")
        self.assertIn('"nested"', js)
        self.assertIn('"display"', js)


class ManualAndArchiveTest(unittest.TestCase):
    def test_manual_edit_writes_new_version_without_overwrite(self):
        tmp, root = make_root()
        self.addCleanup(tmp.cleanup)
        spec_path = add_candidate(root, "manual-a4")
        old = spec_path.read_text(encoding="utf-8")
        spec = json.loads(old)
        spec["name"] = "手动改名"
        result = cli.generate.save_manual(spec_path, spec)
        self.assertTrue(result["ok"])
        self.assertEqual(result["candidate"], "candidate-1-e2")
        self.assertTrue((root / result["spec_path"]).exists())
        self.assertEqual(spec_path.read_text(encoding="utf-8"), old)

    def test_archive_keeps_files_and_blocks_reupload(self):
        tmp, root = make_root()
        self.addCleanup(tmp.cleanup)
        add_candidate(root, "old-a4")
        archived = server.registry.archive("theme", "anime", root=root)
        self.assertTrue(archived["ok"])
        self.assertEqual(server.registry.items("theme", root)["anime"]["status"], "archived")
        with self.assertRaises(display.DisplayError) as ctx:
            display.set_visible("theme", "anime", True, root=root)
        self.assertEqual(ctx.exception.code, "DISPLAY_ARCHIVED")

    def test_clone_published_spec_to_draft(self):
        tmp, root = make_root()
        self.addCleanup(tmp.cleanup)
        (root / "docs" / "templates").mkdir(parents=True)
        source = dict(THEME_SPEC)
        source["key"] = "mist-src"
        (root / "docs" / "templates" / "mist-src.json").write_text(
            json.dumps({"spec": source}, ensure_ascii=False), encoding="utf-8")
        result = cli.generate.clone_published(
            "theme", "mist-src", "mist-v2", "雾青新版",
            docs_dir=root / "docs" / "templates",
            out_dir=root / "tools" / "ai-template" / "drafts")
        self.assertTrue(result["ok"])
        self.assertEqual(result["key"], "mist-v2")
        self.assertTrue((root / "tools" / "ai-template" / "drafts" / "mist-v2" / "candidate-1" / "spec.json").exists())


class HttpSmokeTest(unittest.TestCase):
    def test_generate_and_revise_from_workbench(self):
        tmp, root = make_root()
        self.addCleanup(tmp.cleanup)
        srv = server.make_server(0, root)
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        base = "http://127.0.0.1:%d" % srv.server_address[1]

        req = urllib.request.Request(base + "/api/generate", method="POST",
                                     data=json.dumps({"kind": "layout", "request": "管理台生成",
                                                      "count": 1}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        result = json.loads(urllib.request.urlopen(req, timeout=3).read().decode("utf-8"))
        self.assertTrue(result["ok"])
        self.assertEqual(result["source"], "mock")
        self.assertEqual(len(result["candidates"]), 1)
        spec_path = "tools/ai-template/drafts/%s/candidate-1/spec.json" % result["candidates"][0]["key"]

        req = urllib.request.Request(base + "/api/revise", method="POST",
                                     data=json.dumps({"path": spec_path, "comments": "再紧凑一些",
                                                      "max_rounds": 3}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        revised = json.loads(urllib.request.urlopen(req, timeout=3).read().decode("utf-8"))
        self.assertTrue(revised["ok"])
        self.assertEqual(revised["candidate"], "candidate-1-r2")
        self.assertEqual(revised["round"], 1)
        self.assertTrue((root / revised["review"]).exists())

        old_spec = json.loads((root / revised["spec_path"]).read_text(encoding="utf-8"))
        old_spec["name"] = "HTTP 手改版"
        req = urllib.request.Request(base + "/api/spec/save", method="POST",
                                     data=json.dumps({"path": revised["spec_path"], "spec": old_spec}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        saved = json.loads(urllib.request.urlopen(req, timeout=3).read().decode("utf-8"))
        self.assertTrue(saved["ok"])
        self.assertEqual(saved["candidate"], "candidate-1-r2-e2")

        req = urllib.request.Request(base + "/api/archive", method="POST",
                                     data=json.dumps({"kind": "theme", "key": "anime"}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        archived = json.loads(urllib.request.urlopen(req, timeout=3).read().decode("utf-8"))
        self.assertTrue(archived["ok"])

        (root / "docs" / "templates").mkdir(parents=True, exist_ok=True)
        clone_src = dict(old_spec, key="http-src")
        (root / "docs" / "templates" / "http-src.json").write_text(
            json.dumps({"spec": clone_src}, ensure_ascii=False), encoding="utf-8")
        req = urllib.request.Request(base + "/api/clone", method="POST",
                                     data=json.dumps({"kind": "layout", "key": "http-src",
                                                      "new_key": "http-clone", "new_name": "克隆版"}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        cloned = json.loads(urllib.request.urlopen(req, timeout=3).read().decode("utf-8"))
        self.assertTrue(cloned["ok"])
        self.assertEqual(cloned["key"], "http-clone")

    def test_approve_push_to_display(self):
        tmp, root = make_root()
        self.addCleanup(tmp.cleanup)
        spec_path = add_candidate(root, "push-a4")
        display.set_limit("theme", 8, root=root)
        srv = server.make_server(0, root)
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        base = "http://127.0.0.1:%d" % srv.server_address[1]
        req = urllib.request.Request(base + "/api/approve", method="POST",
                                     data=json.dumps({"path": str(spec_path.relative_to(root)),
                                                      "reviewer": "liyan", "push": True}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        result = json.loads(urllib.request.urlopen(req, timeout=3).read().decode("utf-8"))
        self.assertTrue(result["ok"])
        self.assertTrue(result.get("pushed"))
        self.assertIn("push-a4", display.manage_payload(root=root)["visible"]["visible_themes"])

    def test_candidates_manage_and_display_post(self):
        tmp, root = make_root()
        self.addCleanup(tmp.cleanup)
        add_candidate(root, "http-a4", visual=False, gates_ok=False)
        srv = server.make_server(0, root)
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        base = "http://127.0.0.1:%d" % srv.server_address[1]

        data = json.loads(urllib.request.urlopen(base + "/api/candidates", timeout=3).read().decode("utf-8"))
        self.assertTrue(data["ok"])
        self.assertEqual(data["items"][0]["key"], "http-a4")
        self.assertFalse(data["items"][0]["ok"])
        self.assertIn("AI 设计评审", urllib.request.urlopen(base + "/", timeout=3).read().decode("utf-8"))
        manage = json.loads(urllib.request.urlopen(base + "/api/manage", timeout=3).read().decode("utf-8"))
        self.assertEqual(manage["kinds"]["theme"]["count"], 5)

        req = urllib.request.Request(base + "/api/display/limit", method="POST",
                                     data=json.dumps({"kind": "theme", "max": 8}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        result = json.loads(urllib.request.urlopen(req, timeout=3).read().decode("utf-8"))
        self.assertTrue(result["ok"])
        self.assertEqual(result["max"], 8)

        req = urllib.request.Request(base + "/api/display", method="POST",
                                     data=json.dumps({"kind": "theme", "key": "anime", "on": True}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        result = json.loads(urllib.request.urlopen(req, timeout=3).read().decode("utf-8"))
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()
