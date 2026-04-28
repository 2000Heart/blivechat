# 直播排队机（queue-machine）

blivechat 插件：观众发弹幕 `排队` 入队，`取消排队` 退队；支持粉丝牌门槛、礼物价值动态排序、过号置顶、OBS 展示页与主播管理后台实时同步。

## 安装

将目录放到：

`data/plugins/queue-machine/`

开发态可直接使用仓库已提供的：

`data/plugins/queue-machine/plugin.json`

### 打包为可执行文件（PyInstaller）

见同目录 [BUILD.md](BUILD.md)。在 blivechat 仓库根目录执行：

`python -m PyInstaller -y plugins/queue-machine/queue-machine.spec`

产物在 `dist/queue-machine/`，并生成 `dist/queue-machine.zip`。Windows 分发时 `plugin.json` 的 `run` 与默认一致为 `queue-machine.exe`；macOS 本机构建无 `.exe` 后缀时需按需改写 `run`。

## 启动后地址

- 管理后台：`http://127.0.0.1:18866/admin`
- OBS 展示页：`http://127.0.0.1:18866/overlay`

可在 `plugins/queue-machine/data/config.ini` 修改监听地址和端口。

## 功能说明

- 弹幕指令：`排队` / `取消排队`（可配置）
- 粉丝牌限制：仅 `medal_level >= min_medal_level` 才允许入队
- 排序规则：
  - 过号用户固定置顶，按过号时间升序
  - 普通用户按礼物价值（coin）降序，同值按入队时间升序
- 后台操作：
  - 叫号（设为当前服务）
  - 过号 / 取消过号
  - 移除用户
  - 清空队列（二次确认）
  - 手动修改礼物价值（coin）
- 实时同步：后台与 overlay 均通过 `/ws` 收到快照广播

## 配置项

`plugins/queue-machine/data/config.ini`：

```ini
[queue]
host = 127.0.0.1
port = 18866
min_medal_level = 0
join_keyword = 排队
cancel_keyword = 取消排队
reset_queue_time_on_unpass = true
```

## 验证

在仓库根目录执行：

```bash
python3 -m py_compile plugins/queue-machine/*.py
pytest -q plugins/queue-machine/tests/test_queue_engine.py
```
