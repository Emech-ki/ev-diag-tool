"""
config.py 配置管理测试
覆盖 .env 端点增删改查、数值容错、环境变量解析
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import src.config as config


def _make_getenv(env: dict):
    """构造基于字典的 os.getenv 替换"""
    def f(key, default=None):
        return env.get(key, default)
    return f


class TestEnvHelpers(unittest.TestCase):
    """数值/清洗辅助函数测试"""

    def test_env_float_valid(self):
        with patch.dict(os.environ, {"TEST_F": "0.5"}, clear=False):
            self.assertEqual(config._env_float("TEST_F", 0.7), 0.5)

    def test_env_float_invalid(self):
        with patch.dict(os.environ, {"TEST_F": "abc"}, clear=False):
            self.assertEqual(config._env_float("TEST_F", 0.7), 0.7)

    def test_env_float_missing(self):
        self.assertEqual(config._env_float("TEST_NO_SUCH_KEY", 0.7), 0.7)

    def test_env_int_valid(self):
        with patch.dict(os.environ, {"TEST_I": "2048"}, clear=False):
            self.assertEqual(config._env_int("TEST_I", 1024), 2048)

    def test_env_int_invalid(self):
        with patch.dict(os.environ, {"TEST_I": "x"}, clear=False):
            self.assertEqual(config._env_int("TEST_I", 1024), 1024)

    def test_sanitize_env_value(self):
        self.assertEqual(config._sanitize_env_value("  value  "), "value")
        self.assertEqual(config._sanitize_env_value("a\nb\rc"), "a b c")


class TestGetRemoteEndpoints(unittest.TestCase):
    """get_remote_endpoints 测试"""

    def test_index_format(self):
        env = {
            "OPENAI_ENDPOINT_1_NAME": "DeepSeek",
            "OPENAI_ENDPOINT_1_URL": "https://api.deepseek.com/v1",
            "OPENAI_ENDPOINT_1_KEY": "sk-1",
            "OPENAI_ENDPOINT_1_MODEL": "deepseek-chat",
            "OPENAI_ENDPOINT_2_NAME": "Kimi",
            "OPENAI_ENDPOINT_2_URL": "https://api.moonshot.cn/v1",
            "OPENAI_ENDPOINT_2_KEY": "sk-2",
            # 缺少 url/key 的端点应被跳过
            "OPENAI_ENDPOINT_3_NAME": "NoKey",
            "OPENAI_ENDPOINT_3_URL": "https://x",
        }
        with patch.object(config.os, "getenv", _make_getenv(env)):
            eps = config.get_remote_endpoints()
        self.assertEqual(len(eps), 2)
        self.assertEqual(eps[0]["name"], "DeepSeek")
        self.assertEqual(eps[0]["model_name"], "deepseek-chat")
        self.assertEqual(eps[1]["name"], "Kimi")

    def test_index_default_model(self):
        env = {
            "OPENAI_ENDPOINT_1_NAME": "X",
            "OPENAI_ENDPOINT_1_URL": "https://x/v1",
            "OPENAI_ENDPOINT_1_KEY": "k",
        }
        with patch.object(config.os, "getenv", _make_getenv(env)):
            eps = config.get_remote_endpoints()
        self.assertEqual(eps[0]["model_name"], "gpt-4o-mini")

    def test_legacy_single_endpoint(self):
        with patch.object(config.os, "getenv", _make_getenv({})):
            with patch.object(config, "OPENAI_API_KEY", "sk-legacy"):
                with patch.object(config, "OPENAI_BASE_URL", "https://api.openai.com/v1"):
                    with patch.object(config, "OPENAI_MODEL_NAME", "gpt-4o"):
                        eps = config.get_remote_endpoints()
        self.assertEqual(len(eps), 1)
        self.assertEqual(eps[0]["name"], "OpenAI")
        self.assertEqual(eps[0]["model_name"], "gpt-4o")

    def test_empty(self):
        with patch.object(config.os, "getenv", _make_getenv({})):
            with patch.object(config, "OPENAI_API_KEY", ""):
                eps = config.get_remote_endpoints()
        self.assertEqual(eps, [])


class _TempEnvMixin:
    """把 PROJECT_ROOT 指向临时目录的基类"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self._orig_root = config.PROJECT_ROOT
        self._patch = patch.object(config, "PROJECT_ROOT", Path(self.temp_dir))
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        for name in os.listdir(self.temp_dir):
            os.remove(os.path.join(self.temp_dir, name))
        os.rmdir(self.temp_dir)

    def _write_env(self, lines):
        with open(os.path.join(self.temp_dir, ".env"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def _read_env(self):
        with open(os.path.join(self.temp_dir, ".env"), "r", encoding="utf-8") as f:
            return f.read()


class TestEndpointFileOps(_TempEnvMixin, unittest.TestCase):
    """.env 文件端点增删改查测试"""

    def test_get_next_endpoint_index_no_file(self):
        self.assertEqual(config.get_next_endpoint_index(), 1)

    def test_get_next_endpoint_index_with_entries(self):
        self._write_env([
            "OPENAI_ENDPOINT_1_NAME=A",
            "OPENAI_ENDPOINT_3_NAME=C",
        ])
        self.assertEqual(config.get_next_endpoint_index(), 4)

    def test_append_endpoint(self):
        with patch.object(config, "load_dotenv"):
            idx = config.append_endpoint_to_env("DeepSeek", "https://d/v1", "sk", "deepseek-chat")
        self.assertEqual(idx, 1)
        content = self._read_env()
        self.assertIn("OPENAI_ENDPOINT_1_NAME=DeepSeek", content)
        self.assertIn("OPENAI_ENDPOINT_1_URL=https://d/v1", content)
        self.assertIn("OPENAI_ENDPOINT_1_KEY=sk", content)
        self.assertIn("OPENAI_ENDPOINT_1_MODEL=deepseek-chat", content)

    def test_append_creates_file_when_missing(self):
        with patch.object(config, "load_dotenv"):
            idx = config.append_endpoint_to_env("X", "https://x/v1", "k", "m")
        self.assertEqual(idx, 1)
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, ".env")))

    def test_append_appends_after_existing(self):
        self._write_env(["OPENAI_ENDPOINT_2_NAME=Existing"])
        with patch.object(config, "load_dotenv"):
            idx = config.append_endpoint_to_env("New", "https://n/v1", "k", "m")
        self.assertEqual(idx, 3)
        content = self._read_env()
        self.assertIn("OPENAI_ENDPOINT_3_NAME=New", content)

    def test_remove_endpoint(self):
        self._write_env([
            "OPENAI_ENDPOINT_1_NAME=Keep",
            "OPENAI_ENDPOINT_1_URL=https://keep/v1",
            "OPENAI_ENDPOINT_2_NAME=Remove",
            "OPENAI_ENDPOINT_2_URL=https://remove/v1",
            "OPENAI_ENDPOINT_2_KEY=sk",
            "OPENAI_ENDPOINT_2_MODEL=m",
        ])
        with patch.object(config, "load_dotenv"):
            ok = config.remove_endpoint_from_env("Remove")
        self.assertTrue(ok)
        content = self._read_env()
        self.assertIn("OPENAI_ENDPOINT_1_NAME=Keep", content)
        self.assertNotIn("Remove", content)
        self.assertNotIn("OPENAI_ENDPOINT_2_", content)

    def test_remove_endpoint_not_found(self):
        self._write_env(["OPENAI_ENDPOINT_1_NAME=Keep"])
        with patch.object(config, "load_dotenv"):
            ok = config.remove_endpoint_from_env("Nope")
        self.assertFalse(ok)

    def test_remove_endpoint_no_file(self):
        with patch.object(config, "load_dotenv"):
            ok = config.remove_endpoint_from_env("X")
        self.assertFalse(ok)

    def test_update_endpoint(self):
        self._write_env([
            "OPENAI_ENDPOINT_1_NAME=Target",
            "OPENAI_ENDPOINT_1_URL=https://old/v1",
            "OPENAI_ENDPOINT_1_KEY=oldkey",
            "OPENAI_ENDPOINT_1_MODEL=oldmodel",
        ])
        with patch.object(config, "load_dotenv"):
            ok = config.update_endpoint_in_env("Target", "https://new/v1", "newkey", "newmodel")
        self.assertTrue(ok)
        content = self._read_env()
        self.assertIn("OPENAI_ENDPOINT_1_URL=https://new/v1", content)
        self.assertIn("OPENAI_ENDPOINT_1_KEY=newkey", content)
        self.assertIn("OPENAI_ENDPOINT_1_MODEL=newmodel", content)
        self.assertIn("OPENAI_ENDPOINT_1_NAME=Target", content)

    def test_update_endpoint_not_found(self):
        self._write_env(["OPENAI_ENDPOINT_1_NAME=Target"])
        with patch.object(config, "load_dotenv"):
            ok = config.update_endpoint_in_env("Nope", "u", "k", "m")
        self.assertFalse(ok)

    def test_update_endpoint_no_file(self):
        with patch.object(config, "load_dotenv"):
            ok = config.update_endpoint_in_env("X", "u", "k", "m")
        self.assertFalse(ok)

    def test_sanitize_prevents_injection(self):
        """写入 .env 时换行/回车被清洗，防止注入独立新条目"""
        with patch.object(config, "load_dotenv"):
            config.append_endpoint_to_env("A\nOPENAI_API_KEY=evil", "https://d/v1", "k", "m")
        content = self._read_env()
        # 不应出现以 OPENAI_API_KEY= 开头的独立行
        evil_lines = [ln for ln in content.splitlines() if ln.startswith("OPENAI_API_KEY=evil")]
        self.assertEqual(evil_lines, [])
        # 值在同一行内（换行被替换为空格）
        self.assertIn("NAME=A OPENAI_API_KEY=evil", content)


if __name__ == "__main__":
    unittest.main()
