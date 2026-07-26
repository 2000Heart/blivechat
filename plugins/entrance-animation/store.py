# -*- coding: utf-8 -*-
"""进场动画插件的配置持久化（JSON）。

settings.json 结构：
{
  "users": {
    "<uid>": {"uid": str, "name": str, "animationId": str, "enabled": bool, "cooldownSec": int}
  },
  "animations": {
    "<id>": {"id": str, "name": str, "type": "video|image|gif", "filename": str,
             "durationSec": float, "volume": int}
  },
  "global": {"enabled": bool, "position": str, "size": int, "defaultCooldownSec": int}
}
"""
import copy
import threading
import uuid
from typing import Any, Dict, Optional

import config

_lock = threading.RLock()

_DEFAULT_GLOBAL: Dict[str, Any] = {
    'enabled': True,
    'position': 'center',      # center / top / bottom / left / right / fullscreen
    'size': 480,               # 动画显示的最大边长（px），fullscreen 时忽略
    'defaultCooldownSec': 300,
}

_data: Dict[str, Any] = {'users': {}, 'animations': {}, 'global': dict(_DEFAULT_GLOBAL)}


def _normalize(raw: Dict[str, Any]) -> Dict[str, Any]:
    users = raw.get('users') if isinstance(raw.get('users'), dict) else {}
    animations = raw.get('animations') if isinstance(raw.get('animations'), dict) else {}
    global_cfg = raw.get('global') if isinstance(raw.get('global'), dict) else {}
    merged_global = dict(_DEFAULT_GLOBAL)
    merged_global.update({k: v for k, v in global_cfg.items() if k in _DEFAULT_GLOBAL})
    return {'users': dict(users), 'animations': dict(animations), 'global': merged_global}


def load() -> None:
    global _data
    with _lock:
        _data = _normalize(config._read_json(config.SETTINGS_PATH))


def _save_locked() -> None:
    config._write_json(config.SETTINGS_PATH, _data)


def get_all() -> Dict[str, Any]:
    with _lock:
        return copy.deepcopy(_data)


def get_global() -> Dict[str, Any]:
    with _lock:
        return copy.deepcopy(_data['global'])


def update_global(patch: Dict[str, Any]) -> Dict[str, Any]:
    with _lock:
        for k in _DEFAULT_GLOBAL:
            if k in patch:
                _data['global'][k] = patch[k]
        _save_locked()
        return copy.deepcopy(_data['global'])


def get_user(uid: str) -> Optional[Dict[str, Any]]:
    with _lock:
        user = _data['users'].get(str(uid))
        return copy.deepcopy(user) if user else None


def upsert_user(uid: str, name: str, animation_id: str, enabled: bool,
                cooldown_sec: Optional[int]) -> Dict[str, Any]:
    with _lock:
        uid = str(uid)
        user = {
            'uid': uid,
            'name': name or '',
            'animationId': animation_id or '',
            'enabled': bool(enabled),
            'cooldownSec': int(cooldown_sec) if cooldown_sec not in (None, '') else 0,
        }
        _data['users'][uid] = user
        _save_locked()
        return copy.deepcopy(user)


def delete_user(uid: str) -> bool:
    with _lock:
        if str(uid) in _data['users']:
            del _data['users'][str(uid)]
            _save_locked()
            return True
        return False


def get_animation(animation_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        anim = _data['animations'].get(animation_id)
        return copy.deepcopy(anim) if anim else None


def add_animation(name: str, media_type: str, filename: str,
                  duration_sec: float, volume: int) -> Dict[str, Any]:
    with _lock:
        anim_id = uuid.uuid4().hex
        anim = {
            'id': anim_id,
            'name': name or filename,
            'type': media_type,
            'filename': filename,
            'durationSec': float(duration_sec) if duration_sec else 5.0,
            'volume': int(volume) if volume is not None else 80,
        }
        _data['animations'][anim_id] = anim
        _save_locked()
        return copy.deepcopy(anim)


def update_animation(animation_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    with _lock:
        anim = _data['animations'].get(animation_id)
        if not anim:
            return None
        if 'name' in patch:
            anim['name'] = patch['name']
        if 'durationSec' in patch:
            try:
                anim['durationSec'] = float(patch['durationSec'])
            except (TypeError, ValueError):
                pass
        if 'volume' in patch:
            try:
                anim['volume'] = int(patch['volume'])
            except (TypeError, ValueError):
                pass
        _save_locked()
        return copy.deepcopy(anim)


def delete_animation(animation_id: str) -> Optional[Dict[str, Any]]:
    """删除动画，同时解除引用该动画的用户绑定。返回被删除的动画（含 filename 便于删文件）。"""
    with _lock:
        anim = _data['animations'].pop(animation_id, None)
        if anim is None:
            return None
        for user in _data['users'].values():
            if user.get('animationId') == animation_id:
                user['animationId'] = ''
        _save_locked()
        return copy.deepcopy(anim)
