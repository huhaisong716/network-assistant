"""配置管理 - 服务器列表、API Key 持久化"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional

CONFIG_DIR = os.path.expanduser("~/.nvidia-tool")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
LOG_DIR = os.path.join(CONFIG_DIR, "logs")


@dataclass
class Server:
    name: str = ""
    host: str = ""
    port: int = 22
    user: str = "root"
    key_path: str = "~/.ssh/id_rsa"


@dataclass
class Config:
    servers: list = field(default_factory=list)
    api_key: str = ""
    default_port: int = 22


def get_log_dir() -> str:
    os.makedirs(LOG_DIR, exist_ok=True)
    return LOG_DIR


def load_config() -> Config:
    cfg = Config()
    if not os.path.exists(CONFIG_FILE):
        return cfg
    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            cfg.api_key = data.get("api_key", "")
            cfg.default_port = data.get("default_port", 22)
            for s in data.get("servers", []):
                cfg.servers.append(Server(**s))
    except Exception:
        pass
    return cfg


def save_config(cfg: Config):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    data = {
        "api_key": cfg.api_key,
        "default_port": cfg.default_port,
        "servers": [asdict(s) for s in cfg.servers],
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
