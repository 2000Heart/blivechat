# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import secrets
from dataclasses import asdict, dataclass

BASE_PATH = os.path.dirname(os.path.realpath(__file__))
DATA_PATH = os.path.join(BASE_PATH, "data")
LOG_PATH = os.path.join(BASE_PATH, "log")
WEB_PATH = os.path.join(BASE_PATH, "web")
CONFIG_PATH = os.path.join(DATA_PATH, "config.json")


@dataclass
class AppConfig:
    web_host: str = "127.0.0.1"
    web_port: int = 18766
    require_fans_medal: bool = False
    min_fans_level: int = 0
    require_guard: bool = False
    min_guard_level: int = 1
    max_queue_size: int = 200
    admin_token: str = ""
    overlay_token: str = ""

    def to_public_dict(self) -> dict:
        return {
            "webHost": self.web_host,
            "webPort": self.web_port,
            "requireFansMedal": self.require_fans_medal,
            "minFansLevel": self.min_fans_level,
            "requireGuard": self.require_guard,
            "minGuardLevel": self.min_guard_level,
            "maxQueueSize": self.max_queue_size,
        }


_config: AppConfig | None = None


def init() -> None:
    os.makedirs(DATA_PATH, exist_ok=True)
    os.makedirs(LOG_PATH, exist_ok=True)
    if not reload():
        global _config
        cfg = AppConfig()
        cfg.admin_token = secrets.token_hex(16)
        cfg.overlay_token = secrets.token_hex(16)
        _config = cfg
        save()


def reload() -> bool:
    if not os.path.exists(CONFIG_PATH):
        return False
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False

    cfg = AppConfig(
        web_host=str(raw.get("webHost", "127.0.0.1")),
        web_port=int(raw.get("webPort", 18766)),
        require_fans_medal=bool(raw.get("requireFansMedal", False)),
        min_fans_level=max(0, int(raw.get("minFansLevel", 0))),
        require_guard=bool(raw.get("requireGuard", False)),
        min_guard_level=max(1, int(raw.get("minGuardLevel", 1))),
        max_queue_size=max(1, int(raw.get("maxQueueSize", 200))),
        admin_token=str(raw.get("adminToken", "")),
        overlay_token=str(raw.get("overlayToken", "")),
    )
    if cfg.admin_token == "":
        cfg.admin_token = secrets.token_hex(16)
    if cfg.overlay_token == "":
        cfg.overlay_token = secrets.token_hex(16)

    global _config
    _config = cfg
    return True


def save() -> None:
    cfg = get_config()
    raw = asdict(cfg)
    payload = {
        "webHost": raw["web_host"],
        "webPort": raw["web_port"],
        "requireFansMedal": raw["require_fans_medal"],
        "minFansLevel": raw["min_fans_level"],
        "requireGuard": raw["require_guard"],
        "minGuardLevel": raw["min_guard_level"],
        "maxQueueSize": raw["max_queue_size"],
        "adminToken": raw["admin_token"],
        "overlayToken": raw["overlay_token"],
    }
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_PATH)


def update_from_payload(payload: dict) -> AppConfig:
    cfg = get_config()
    if "requireFansMedal" in payload:
        cfg.require_fans_medal = bool(payload["requireFansMedal"])
    if "minFansLevel" in payload:
        cfg.min_fans_level = max(0, int(payload["minFansLevel"]))
    if "requireGuard" in payload:
        cfg.require_guard = bool(payload["requireGuard"])
    if "minGuardLevel" in payload:
        cfg.min_guard_level = max(1, int(payload["minGuardLevel"]))
    if "maxQueueSize" in payload:
        cfg.max_queue_size = max(1, int(payload["maxQueueSize"]))
    save()
    return cfg


def get_config() -> AppConfig:
    assert _config is not None
    return _config
