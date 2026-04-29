# 数据分析插件（data-analytics）

用于持久化直播消息并提供本地可视化看板。插件会将弹幕、礼物、上舰、醒目留言写入 SQLite，并通过内置 HTTP API 给前端看板查询。

## 快速开始

### 方式一：使用打包版（推荐）

1. 按 [BUILD.md](BUILD.md) 构建插件。
2. 将产物目录放到 `data/plugins/data-analytics/`。
3. 在 blivechat 插件管理中启用插件。
4. 点击插件 `Admin UI`，浏览器会直接打开数据看板。

### 方式二：源码运行

1. 将插件目录放到 `data/plugins/data-analytics/`。
2. 将 `plugin.json` 的 `run` 改为 `python -u main.py`。
3. 从项目根目录启动 blivechat，并在插件管理中启用本插件。

## 管理页与配置

- 默认地址：`http://127.0.0.1:18766/?token=...`
- 配置文件：`data/web_config.json`
  - `host`
  - `port`
  - `adminToken`
- 点击 `Admin UI` 会自动拼接 token 打开看板，无需手动选择数据库文件。

## 本地 API

服务默认监听本机（`127.0.0.1`），当前仅保留 `/api/v2/*`。  
`/api/v1/*` 已下线，访问时返回 `410 Gone`。

常用查询参数：

- `room_id`
- `from_ts` / `to_ts`（Unix 秒）
- `source`（`all` / `bilibili` / `douyin`）
- `limit` / `offset`

鉴权方式：

- `?token=...`，或
- `Authorization: Bearer <token>`

**说明**：所有 `/api/` 前缀接口均需上述鉴权。

### API v2（看板多维分析，数据来自 `analytics_v2.db`）

插件启动时会自动执行旧库迁移（若存在 `analytics.db`），并切换为 v2-only 存储。

- `GET /api/v2/kpis`：营收与人数类 KPI
- `GET /api/v2/trend/revenue`：按日/周/月的营收趋势
- `GET /api/v2/segments/users`：按贡献金额的用户分层计数
- `GET /api/v2/explore/events`：统一事件流明细分页
- `GET /api/v2/series/active-hour-of-day`：**跨日期按 0–23 点叠加**的活跃分析；统计 **弹幕 + 礼物** 事件条数，并返回每小时 **去重用户数**（优先 `uid`，否则 `author_name`）。时间桶使用 **服务器本地时区**（`meta.timezoneNote` 为 `local_server`）。
- `GET /api/v2/rankings/danmaku-authors?limit=`：弹幕条数排行
- `GET /api/v2/rankings/gift-authors?limit=&sort=count|amount`：送礼次数或金额排行
- `GET /api/v2/users/danmaku?uid=&author_name=&limit=&offset=`：某用户在筛选条件下的弹幕分页（`uid` 与 `author_name` 二选一必填；有 `uid` 时按 `uid` 匹配）
- `GET /api/v2/users/gifts?uid=&author_name=&limit=&offset=`：同上，礼物明细分页

v2 常用查询参数：`room_id`、`from_ts` / `to_ts`、`source`、`limit` / `offset`，以及 `view_mode`、`granularity`（见前端全局上下文）。

## 数据库结构

数据库文件：`data/plugins/data-analytics/data/analytics_v2.db`（唯一读写库）

### 表：`rooms`

- `room_id` INTEGER PRIMARY KEY
- `room_key_type` INTEGER NOT NULL（1=房间ID,2=身份码）
- `room_key_value` TEXT NOT NULL
- `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

### v2 数据库：`analytics_v2.db`

- 路径：`data/plugins/data-analytics/data/analytics_v2.db`
- 由脚本 `python3 migrate_v2.py`（可加 `--full` 清空 v2 事实表后全量导入）从 `analytics.db` 导入到表 `fact_events`。
- 弹幕文本存于 `fact_events.content`（仅 `event_type=danmaku` 时有值）。

### 表：`danmaku`

- `id` TEXT PRIMARY KEY
- `room_id` INTEGER NOT NULL
- `timestamp` INTEGER NOT NULL
- `uid` TEXT
- `author_name` TEXT NOT NULL
- `author_type` INTEGER NOT NULL
- `author_level` INTEGER NOT NULL
- `content` TEXT NOT NULL
- `translation` TEXT
- `is_gift_danmaku` INTEGER NOT NULL DEFAULT 0
- `is_newbie` INTEGER NOT NULL DEFAULT 0
- `is_mobile_verified` INTEGER NOT NULL DEFAULT 1
- `privilege_type` INTEGER NOT NULL DEFAULT 0
- `medal_level` INTEGER NOT NULL DEFAULT 0
- `medal_name` TEXT
- `content_type` INTEGER NOT NULL DEFAULT 0
- `avatar_url` TEXT
- `source` TEXT NOT NULL DEFAULT `'bilibili'`
- `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

### 表：`gifts`

- `id` TEXT PRIMARY KEY
- `room_id` INTEGER NOT NULL
- `timestamp` INTEGER NOT NULL
- `uid` TEXT
- `author_name` TEXT NOT NULL
- `gift_id` INTEGER NOT NULL
- `gift_name` TEXT NOT NULL
- `gift_icon_url` TEXT
- `num` INTEGER NOT NULL
- `total_coin` INTEGER NOT NULL DEFAULT 0
- `total_free_coin` INTEGER NOT NULL DEFAULT 0
- `privilege_type` INTEGER NOT NULL DEFAULT 0
- `medal_level` INTEGER NOT NULL DEFAULT 0
- `medal_name` TEXT
- `avatar_url` TEXT
- `source` TEXT NOT NULL DEFAULT `'bilibili'`
- `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

### 表：`members`

- `id` TEXT PRIMARY KEY
- `room_id` INTEGER NOT NULL
- `timestamp` INTEGER NOT NULL
- `uid` TEXT
- `author_name` TEXT NOT NULL
- `privilege_type` INTEGER NOT NULL
- `num` INTEGER NOT NULL
- `unit` TEXT NOT NULL
- `total_coin` INTEGER NOT NULL
- `medal_level` INTEGER NOT NULL DEFAULT 0
- `medal_name` TEXT
- `avatar_url` TEXT
- `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

### 表：`super_chat`

- `id` TEXT PRIMARY KEY
- `room_id` INTEGER NOT NULL
- `timestamp` INTEGER NOT NULL
- `uid` TEXT
- `author_name` TEXT NOT NULL
- `price` INTEGER NOT NULL
- `content` TEXT NOT NULL
- `translation` TEXT
- `privilege_type` INTEGER NOT NULL DEFAULT 0
- `medal_level` INTEGER NOT NULL DEFAULT 0
- `medal_name` TEXT
- `avatar_url` TEXT
- `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

### 索引

- `idx_danmaku_room_time`、`idx_danmaku_uid`
- `idx_gifts_room_time`、`idx_gifts_uid`
- `idx_members_room_time`、`idx_members_uid`
- `idx_super_chat_room_time`、`idx_super_chat_uid`

## 前端开发

```bash
cd plugins/data-analytics/dashboard
npm install
npm run dev
```

构建：

```bash
cd plugins/data-analytics/dashboard
npm run build
```

构建产物会输出到 `plugins/data-analytics/web/dist`，运行时优先加载该目录。

## 命令行分析脚本

```bash
python analyze.py
python analyze.py 123456
python analyze.py --all
```

## 注意事项

- 数据库会持续增长，建议定期备份或清理历史数据。
- 默认绑定本机地址并使用 token 鉴权，不建议对公网暴露。

