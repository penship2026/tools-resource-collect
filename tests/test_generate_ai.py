#!/usr/bin/env python3
"""A2 生成管线测试：mock 双类型、3 候选、缓存、非法 JSON 重试、合成样例边界。"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock as unittest_mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "ai-template"))

import cli  # noqa: E402
import compiler  # noqa: E402
import theme_lint  # noqa: E402
from adapters import mock as mock_adapter  # noqa: E402
from adapters import openai_compat  # noqa: E402

generate = cli.generate


class FixedAdapter:
    source = "model"
    model = "fixed-test"

    def __init__(self, text):
        self.text = text
        self.calls = 0

    def complete(self, system, user, kind=None):
        self.calls += 1
        return self.text


class FlakyAdapter(FixedAdapter):
    def __init__(self, first, then):
        super().__init__(then)
        self.first = first

    def complete(self, system, user, kind=None):
        self.calls += 1
        return self.first if self.calls == 1 else self.text


class SameLayoutAdapter(FixedAdapter):
    def complete(self, system, user, kind=None):
        self.calls += 1
        items = generate.parse_candidates(mock_adapter.complete(system, user, "layout"))
        base = items[0]
        out = []
        for i, key in enumerate(("same-a", "same-b", "same-c")):
            item = json.loads(json.dumps(base))
            item["key"] = key
            out.append(item)
        return json.dumps(out)


class GenerateAITest(unittest.TestCase):
    def test_mock_layout_three_valid_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = generate.generate("layout", "3 列门户，移动端不溢出", mock=True,
                                    out_dir=Path(tmp) / "out", cache_dir=Path(tmp) / "cache")
        self.assertEqual(run["source"], "mock")
        self.assertEqual(len(run["candidates"]), 3)
        self.assertEqual(len({c["key"] for c in run["candidates"]}), 3)
        self.assertTrue(all(c["css_bytes"] > 0 for c in run["candidates"]))
        self.assertEqual({c["kind"] for c in run["candidates"]}, {"layout"})

    def test_mock_theme_lint_and_three_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = generate.generate("theme", "暖色纸张质感", mock=True,
                                    out_dir=Path(tmp) / "out", cache_dir=Path(tmp) / "cache")
            for cand in run["candidates"]:
                css = (Path(tmp) / "out" / cand["css"]).read_text(encoding="utf-8")
                self.assertEqual(theme_lint.lint_theme_css(css), [], cand["key"])
        self.assertEqual(len(run["candidates"]), 3)

    def test_cache_hit_second_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            kw = dict(mock=True, out_dir=Path(tmp) / "out", cache_dir=Path(tmp) / "cache")
            first = generate.generate("layout", "缓存测试", **kw)
            second = generate.generate("layout", "缓存测试", **kw)
        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])
        self.assertEqual(first["prompt_sha256"], second["prompt_sha256"])

    def test_invalid_json_then_retry_succeeds(self):
        adapter = FlakyAdapter("这不是 JSON", mock_adapter.complete("", "", "layout"))
        with tempfile.TemporaryDirectory() as tmp:
            run = generate.generate("layout", "重试", adapter=adapter,
                                    out_dir=Path(tmp) / "out", cache_dir=Path(tmp) / "cache",
                                    attempts=2)
        self.assertEqual(adapter.calls, 2)
        self.assertEqual(len(run["candidates"]), 3)

    def test_schema_error_then_retry_succeeds(self):
        bad = json.loads(mock_adapter.complete("", "", "layout"))
        bad[0]["density"] = "crazy"
        adapter = FlakyAdapter(json.dumps(bad, ensure_ascii=False),
                               mock_adapter.complete("", "", "layout"))
        with tempfile.TemporaryDirectory() as tmp:
            run = generate.generate("layout", "schema 重试", adapter=adapter,
                                    out_dir=Path(tmp) / "out", cache_dir=Path(tmp) / "cache")
        self.assertEqual(adapter.calls, 2)
        self.assertEqual(len(run["candidates"]), 3)

    def test_same_candidates_rejected(self):
        adapter = SameLayoutAdapter("")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(generate.GenerationError) as ctx:
                generate.generate("layout", "重复", adapter=adapter,
                                  out_dir=Path(tmp) / "out", cache_dir=Path(tmp) / "cache")
        self.assertEqual(adapter.calls, 2)
        self.assertTrue(any("只差" in e for e in ctx.exception.errors))

    def test_prompt_uses_synthetic_sample_only(self):
        user = generate.build_user_prompt("layout", "测试")
        self.assertIn(generate.SAMPLE_ID, user)
        for forbidden in ("jiye.mine.v1", "http://", "https://", "author", "收藏原文"):
            self.assertNotIn(forbidden, user)

    def test_from_env_requires_all_three(self):
        with unittest_mock.patch.dict(os.environ, {"AI_BASE_URL": "https://x", "AI_API_KEY": "k"}, clear=True):
            self.assertIsNone(openai_compat.from_env())
        with unittest_mock.patch.dict(os.environ, {"AI_BASE_URL": "https://x", "AI_API_KEY": "k", "AI_MODEL": "m"}, clear=True):
            self.assertIsNotNone(openai_compat.from_env())

    def test_cli_generate_mock(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = cli.main(["generate", "--kind", "layout", "--request", "CLI 冒烟",
                                 "--mock", "--out", tmp, "--no-cache"])
            self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["source"], "mock")
        self.assertEqual(len(payload["candidates"]), 3)


if __name__ == "__main__":
    unittest.main()
