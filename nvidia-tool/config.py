"""服务器和 API Key 配置持久化"""
import os
import json
import stat
from pathlib import Path

CONFIG_DIR = Path.home() / ".nvidia-tool"
CONFIG_FILE = CONFIG_DIR / "config.json"


def _ensure_config():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        with open(CONFIG_FILE, "w") as f:
            json.dump({"servers": [], "deepseek_api_key": ""}, f, indent=2)
        # 安全权限
        os.chmod(str(CONFIG_FILE), stat.S_IRUSR | stat.S_IWUSR)


def load() -> dict:
    _ensure_config()
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save(data: dict):
    _ensure_config()
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)
    os.chmod(str(CONFIG_FILE), stat.S_IRUSR | stat.S_IWUSR)


def get_servers() -> list[dict]:
    """返回 [{name, host, port, user, auth_type, key_path|password}, ...]"""
    return load().get("servers", [])


def add_server(server: dict):
    data = load()
    # 同名替换
    data["servers"] = [s for s in data["servers"] if s.get("name") != server.get("name")]
    data["servers"].append(server)
    save(data)


def remove_server(name: str):
    data = load()
    data["servers"] = [s for s in data["servers"] if s.get("name") != name]
    save(data)


def get_deepseek_key() -> str:
    return load().get("deepseek_api_key", "")


def set_deepseek_key(key: str):
    data = load()
    data["deepseek_api_key"] = key
    save(data)
