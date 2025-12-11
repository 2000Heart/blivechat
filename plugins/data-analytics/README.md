# 数据分析插件

这个插件用于保存直播弹幕数据到SQLite数据库，便于后续进行数据分析。

## 功能特性

- **完整数据保存**：保存所有类型的消息数据
  - 弹幕（danmaku）
  - 礼物（gifts）
  - 上舰（members）
  - 醒目留言（super_chat）

- **结构化存储**：使用SQLite数据库存储，便于查询和分析
- **丰富的数据字段**：包含用户信息、时间戳、内容等完整信息
- **高性能索引**：为常用查询字段创建索引，提高查询速度

## 安装和使用

### 方法一：使用打包的 exe 文件（推荐）

1. 按照 [BUILD.md](BUILD.md) 中的说明打包插件为 exe 文件
2. 将打包后的文件放到 `data/plugins/data-analytics/` 目录下
3. 在blivechat的插件管理界面启用插件
4. 插件会自动开始保存数据到 `data/plugins/data-analytics/data/analytics.db`

### 方法二：直接使用 Python 脚本

1. 将插件目录放到 `data/plugins/data-analytics/` 目录下
2. 确保blivechat项目在Python路径中（通常从项目根目录运行blivechat会自动满足）
3. 修改 `plugin.json` 中的 `run` 字段为 `"run": "python -u main.py"`
4. 在blivechat的插件管理界面启用插件
5. 插件会自动开始保存数据到 `data/plugins/data-analytics/data/analytics.db`

### 方法三：修改运行命令

如果无法直接导入blcsdk，可以修改 `plugin.json` 中的 `run` 字段：

```json
{
  "run": "python -c \"import sys; sys.path.insert(0, '/path/to/blivechat'); exec(open('main.py').read())\""
}
```

将 `/path/to/blivechat` 替换为实际的blivechat项目路径。

### 使用数据分析脚本

运行分析脚本查看统计数据：

```bash
# 查看所有房间
python analyze.py

# 分析指定房间
python analyze.py 123456

# 分析所有房间
python analyze.py --all
```

## 数据库结构

### rooms 表
存储房间信息
- `room_id`: 房间ID（主键）
- `room_key_type`: 房间键类型（1=房间ID, 2=身份码）
- `room_key_value`: 房间键值
- `created_at`: 创建时间

### danmaku 表
存储弹幕数据
- `id`: 消息ID（主键）
- `room_id`: 房间ID
- `timestamp`: 时间戳（秒）
- `uid`: 用户ID
- `author_name`: 用户名
- `author_type`: 用户类型（0=普通, 1=舰队, 2=房管, 3=主播）
- `author_level`: 用户等级
- `content`: 弹幕内容
- `translation`: 翻译内容
- `is_gift_danmaku`: 是否礼物弹幕
- `is_newbie`: 是否新用户
- `is_mobile_verified`: 是否绑定手机
- `privilege_type`: 舰队等级
- `medal_level`: 勋章等级
- `medal_name`: 勋章名称
- `content_type`: 内容类型（0=文本, 1=表情）
- `avatar_url`: 头像URL

### gifts 表
存储礼物数据
- `id`: 消息ID（主键）
- `room_id`: 房间ID
- `timestamp`: 时间戳
- `uid`: 用户ID
- `author_name`: 用户名
- `gift_id`: 礼物ID
- `gift_name`: 礼物名称
- `gift_icon_url`: 礼物图标URL
- `num`: 数量
- `total_coin`: 总价（金瓜子，1000=1元）
- `total_free_coin`: 总价（银瓜子）
- `privilege_type`: 舰队等级
- `medal_level`: 勋章等级
- `medal_name`: 勋章名称
- `avatar_url`: 头像URL

### members 表
存储上舰数据
- `id`: 消息ID（主键）
- `room_id`: 房间ID
- `timestamp`: 时间戳
- `uid`: 用户ID
- `author_name`: 用户名
- `privilege_type`: 舰队等级（1=总督, 2=提督, 3=舰长）
- `num`: 数量
- `unit`: 单位（月）
- `total_coin`: 总价（金瓜子）
- `medal_level`: 勋章等级
- `medal_name`: 勋章名称
- `avatar_url`: 头像URL

### super_chat 表
存储醒目留言数据
- `id`: 消息ID（主键）
- `room_id`: 房间ID
- `timestamp`: 时间戳
- `uid`: 用户ID
- `author_name`: 用户名
- `price`: 价格（元）
- `content`: 内容
- `translation`: 翻译内容
- `privilege_type`: 舰队等级
- `medal_level`: 勋章等级
- `medal_name`: 勋章名称
- `avatar_url`: 头像URL

## 数据分析示例

### 使用Python分析数据

```python
import sqlite3
from datetime import datetime

# 连接数据库
conn = sqlite3.connect('data/plugins/data-analytics/data/analytics.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 查询某个房间的弹幕数量
room_id = 123456
cursor.execute('SELECT COUNT(*) FROM danmaku WHERE room_id = ?', (room_id,))
danmaku_count = cursor.fetchone()[0]
print(f'弹幕总数: {danmaku_count}')

# 查询礼物统计
cursor.execute('''
    SELECT gift_name, SUM(num) as total_num, SUM(total_coin) as total_coin
    FROM gifts
    WHERE room_id = ?
    GROUP BY gift_name
    ORDER BY total_coin DESC
    LIMIT 10
''', (room_id,))
print('礼物排行:')
for row in cursor.fetchall():
    print(f"  {row['gift_name']}: {row['total_num']}个, {row['total_coin']/1000:.2f}元")

# 查询活跃用户
cursor.execute('''
    SELECT author_name, COUNT(*) as count
    FROM danmaku
    WHERE room_id = ?
    GROUP BY uid, author_name
    ORDER BY count DESC
    LIMIT 10
''', (room_id,))
print('活跃用户:')
for row in cursor.fetchall():
    print(f"  {row['author_name']}: {row['count']}条弹幕")

# 查询时间段统计
cursor.execute('''
    SELECT 
        strftime('%Y-%m-%d %H:00:00', datetime(timestamp, 'unixepoch')) as hour,
        COUNT(*) as count
    FROM danmaku
    WHERE room_id = ?
    GROUP BY hour
    ORDER BY hour
''', (room_id,))
print('时间段统计:')
for row in cursor.fetchall():
    print(f"  {row['hour']}: {row['count']}条弹幕")

conn.close()
```

### 使用SQL查询

```sql
-- 查询所有房间的弹幕总数
SELECT room_id, COUNT(*) as danmaku_count
FROM danmaku
GROUP BY room_id;

-- 查询某个时间段的弹幕
SELECT * FROM danmaku
WHERE room_id = 123456
  AND timestamp >= UNIX_TIMESTAMP('2024-01-01 00:00:00')
  AND timestamp < UNIX_TIMESTAMP('2024-01-02 00:00:00');

-- 查询礼物价值排行
SELECT gift_name, SUM(total_coin) as total_value
FROM gifts
WHERE room_id = 123456
GROUP BY gift_name
ORDER BY total_value DESC;

-- 查询上舰统计
SELECT 
    CASE privilege_type
        WHEN 1 THEN '总督'
        WHEN 2 THEN '提督'
        WHEN 3 THEN '舰长'
        ELSE '未知'
    END as guard_type,
    COUNT(*) as count,
    SUM(total_coin) as total_value
FROM members
WHERE room_id = 123456
GROUP BY privilege_type;
```

## 注意事项

- 数据库文件会持续增长，建议定期备份
- 可以通过SQL删除旧数据来清理空间
- 插件默认禁用，需要在插件管理中启用
- 确保有足够的磁盘空间存储数据

