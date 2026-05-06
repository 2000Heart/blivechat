import configparser
import os
from dataclasses import dataclass

BASE_PATH = os.path.dirname(os.path.realpath(__file__))
DATA_PATH = os.path.join(BASE_PATH, "data")
LOG_PATH = os.path.join(BASE_PATH, "log")
WEB_PATH = os.path.join(BASE_PATH, "web")
STATE_PATH = os.path.join(DATA_PATH, "queue_state.json")
CONFIG_PATH = os.path.join(DATA_PATH, "config.ini")


@dataclass
class AppConfig:
    host: str = "127.0.0.1"
    port: int = 18866
    min_medal_level: int = 0
    join_keyword: str = "排队"
    cancel_keyword: str = "取消排队"
    reset_queue_time_on_unpass: bool = True
    board_color: str = "#000000"
    board_opacity: float = 0.0
    board_radius: int = 0
    item_color: str = "#000000"
    item_opacity: float = 0.5
    item_radius: int = 10
    banner_text: str = ""
    banner_font_size: int = 15
    captain_priority_enabled: bool = True


_cfg = AppConfig()


def init() -> None:
    os.makedirs(DATA_PATH, exist_ok=True)
    os.makedirs(LOG_PATH, exist_ok=True)
    if not os.path.isfile(CONFIG_PATH):
        save()
    reload()


def reload() -> None:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(CONFIG_PATH, encoding="utf-8")
    sec = parser["queue"] if parser.has_section("queue") else {}
    global _cfg
    _cfg = AppConfig(
        host=str(sec.get("host", "127.0.0.1")),
        port=int(sec.get("port", 18866)),
        min_medal_level=max(0, int(sec.get("min_medal_level", 0))),
        join_keyword=str(sec.get("join_keyword", "排队")).strip() or "排队",
        cancel_keyword=str(sec.get("cancel_keyword", "取消排队")).strip() or "取消排队",
        reset_queue_time_on_unpass=bool(
            str(sec.get("reset_queue_time_on_unpass", "true")).strip().lower() in ("1", "true", "yes", "on")
        ),
        board_color=str(sec.get("board_color", "#000000")).strip() or "#000000",
        board_opacity=float(sec.get("board_opacity", 0.0)),
        board_radius=max(0, int(sec.get("board_radius", 0))),
        item_color=str(sec.get("item_color", "#000000")).strip() or "#000000",
        item_opacity=float(sec.get("item_opacity", 0.5)),
        item_radius=max(0, int(sec.get("item_radius", 10))),
        banner_text=str(sec.get("banner_text", ""))[:200],
        banner_font_size=max(12, min(64, int(sec.get("banner_font_size", 15)))),
        captain_priority_enabled=bool(
            str(sec.get("captain_priority_enabled", "true")).strip().lower() in ("1", "true", "yes", "on")
        ),
    )


def save() -> None:
    parser = configparser.ConfigParser(interpolation=None)
    parser["queue"] = {
        "host": _cfg.host,
        "port": str(_cfg.port),
        "min_medal_level": str(_cfg.min_medal_level),
        "join_keyword": _cfg.join_keyword,
        "cancel_keyword": _cfg.cancel_keyword,
        "reset_queue_time_on_unpass": "true" if _cfg.reset_queue_time_on_unpass else "false",
        "board_color": _cfg.board_color,
        "board_opacity": str(_cfg.board_opacity),
        "board_radius": str(_cfg.board_radius),
        "item_color": _cfg.item_color,
        "item_opacity": str(_cfg.item_opacity),
        "item_radius": str(_cfg.item_radius),
        "banner_text": _cfg.banner_text,
        "banner_font_size": str(_cfg.banner_font_size),
        "captain_priority_enabled": "true" if _cfg.captain_priority_enabled else "false",
    }
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        parser.write(f)


def get_config() -> AppConfig:
    return _cfg
