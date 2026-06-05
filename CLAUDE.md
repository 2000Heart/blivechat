# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```sh
# Run backend server
python main.py
python main.py --host 127.0.0.1 --port 12450

# Build frontend (Node.js required)
cd frontend && npm i && npm run build

# Frontend dev server (proxies API to 127.0.0.1:12450)
cd frontend && npm run serve

# Lint
cd frontend && npm run lint

# Docker
docker run --name blivechat -d -p 12450:12450 \
  --mount source=blivechat-data,target=/mnt/data \
  xfgryujk/blivechat:latest

# Update blivedm submodule
git submodule update --init --recursive
```

## Architecture

**blivechat** is a YouTube-style bilibili live chat overlay for OBS. It provides a WebSocket proxy between bilibili's live danmaku servers and browser-based overlays, with translation, avatar caching, and plugin support.

### Backend (Python/Tornado async)

```
main.py                  # Entry point: Tornado server, route registration, signal handling
config.py                # INI-based config management (data/config.ini)
api/                     # HTTP + WebSocket API handlers
  chat.py                #   WebSocket for live chat relay + REST for room info/avatar/text emoticons
  main.py                #   Server info, template listing, emoticon upload
  open_live.py           #   Bilibili Open Platform API
  plugin.py              #   Plugin WebSocket API
services/                # Business logic
  chat.py                #   Live client & client room managers, message handling, reconnection logic
  translate.py           #   Translation engine (Tencent/Baidu/OpenAI API)
  avatar.py              #   Avatar fetching with LRU cache
  open_live.py           #   Open Platform heartbeat/game lifecycle
  plugin.py              #   Plugin subprocess lifecycle & message routing
models/                  # SQLAlchemy models + SQLite engine
  database.py            #   DB engine init, ORM base class
utils/                   # Helpers
  request.py             #   Shared aiohttp session
  async_io.py            #   Task ref management
  rate_limit.py          #   Token bucket rate limiter
blivedm/                 # Git submodule: bilibili live WebSocket danmaku client library
blcsdk/                  # Plugin SDK (message models, client API, handlers)
```

**Connection modes** (determined by client-side):
1. Direct WebSocket from browser to bilibili (ChatClientDirectWeb)
2. Direct via bilibili Open Platform from browser (ChatClientDirectOpenLive)
3. Relay via backend (ChatClientRelay) — browser → Tornado WebSocket → bilibili

**Key flow**: ChatHandler (WebSocket) → ClientRoomManager → LiveClientManager → blivedm (WebSocket to bilibili). Messages flow back through LiveMsgHandler → ClientRoom → ChatHandler → browser.

### Frontend (Vue 2 + Element UI)

```
frontend/src/
  views/                 # Pages
    Home/                # Landing page: room key input, template selection
    Room.vue             # Main room view: chat renderer + custom template iframe
    ChatRenderer/        # Standalone chat display for template development
    StyleGenerator/      # CSS style generators (YouTube-style & WeChat-style)
    Plugins.vue          # Plugin management
    Help.vue             # Help page
  components/ChatRenderer/  # Chat UI: TextMessage, PaidMessage, MembershipItem, Ticker, badges
  api/chat/              # Chat client implementations (DirectWeb, DirectOpenLive, Relay, Test)
  lang/                  # i18n (zh, en, ja)
  layout/                # Sidebar layout
```

Real-time chat data is sent as compact arrays (not dicts) over WebSocket to save bandwidth — see `api/chat.py:make_text_message_data()` for the array schema (19-element list). Frontend hydrates these into typed message objects in `frontend/src/api/chat/models.js`.

### Plugin System

Plugins are subprocesses launched by the backend, configured via `data/plugins/<id>/plugin.json`:

```json
{"name": "...", "version": "...", "run": "python main.py", "enabled": true}
```

Environment: `BLC_PORT` + `BLC_TOKEN`. Plugins connect via WebSocket to the backend and exchange typed messages (blcsdk models). Message forwarding to all plugins happens through `services.plugin.broadcast_cmd_data()`.

Built-in plugins: `queue-machine`, `native-ui`, `douyin-relay`, `login`, `msg-logging`, `text-to-speech`.

### Custom HTML Templates

Templates live in `data/custom_public/templates/<id>/` with a `template.json` config file. They render in an iframe and communicate via `postMessage` API. Built-in templates: `youtube`, `liquid-glass`, `zzz`.

## Key Data Structures

- **RoomKey**: Identifies a room by either room_id (int) or auth_code (str)
- **Text message array (from backend → frontend)**: `[avatarUrl, timestamp, authorName, authorType, content, privilegeType, isGiftDanmaku, authorLevel, isNewbie, isMobileVerified, medalLevel, id, translation, contentType, contentTypeParams, textEmoticons (deprecated), uid, medalName, isMirror, identityExt]`
- **Commands**: HEARTBEAT(0), JOIN_ROOM(1), ADD_TEXT(2), ADD_GIFT(3), ADD_MEMBER(4), ADD_SUPER_CHAT(5), DEL_SUPER_CHAT(6), UPDATE_TRANSLATION(7), FATAL_ERROR(8)
