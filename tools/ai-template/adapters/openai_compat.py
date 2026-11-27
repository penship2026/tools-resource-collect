"""A2 模型适配层：OpenAI 兼容端点与离线 mock 共用 complete(system, user, kind)。"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path


ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load_env_file(path=None):
    """读取本机 .env（git 忽略）；只补未设置的变量，不覆盖 shell。"""
    path = Path(path) if path else ENV_FILE
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and value and key not in os.environ:
            os.environ[key] = value


class AdapterError(RuntimeError):
    pass


class OpenAICompat:
    source = "model"

    def __init__(self, base_url, api_key, model, timeout=60):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.model = model or ""
        try:
            self.timeout = int(timeout or 60)
        except (TypeError, ValueError):
            self.timeout = 60

    def complete(self, system, user, kind=None):
        if not self.base_url or not self.api_key or not self.model:
            raise AdapterError("缺少 AI_BASE_URL / AI_API_KEY / AI_MODEL")
        endpoint = self.base_url
        if not endpoint.endswith("/chat/completions"):
            endpoint += "/chat/completions"
        payload = {
            "model": self.model,
            "temperature": 0.4,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self.api_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise AdapterError("模型接口 HTTP %s" % exc.code) from exc
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise AdapterError("模型接口不可用:%s" % exc) from exc
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AdapterError("模型响应缺少 choices[0].message.content") from exc
        if not isinstance(content, str):
            raise AdapterError("模型 content 不是字符串")
        return content


def from_env():
    """按环境变量决定适配器；没有完整配置时返回 None，由调用方降级 mock。"""
    load_env_file()
    base = os.environ.get("AI_BASE_URL", "")
    key = os.environ.get("AI_API_KEY", "")
    model = os.environ.get("AI_MODEL", "")
    if base and key and model:
        return OpenAICompat(base, key, model, os.environ.get("AI_TIMEOUT", "60"))
    return None
